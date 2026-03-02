# api/appointments/show_appointments.py

from datetime import datetime, timezone
import logging
import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr

from api.authz import authorize_client_request
from api.config.config import supabase
from api.appointments.template_language_resolution import normalize_language_preferences

router = APIRouter(prefix="/appointments", tags=["Appointments"])

logger = logging.getLogger(__name__)
E164_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


class AppointmentClientPayload(BaseModel):
    client_id: UUID
    user_name: str
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_locale: Optional[str] = None


def _is_valid_datetime(value) -> bool:
    if not value or not isinstance(value, str):
        return False
    raw = value.strip()
    if not raw:
        return False
    try:
        normalized = raw.replace("Z", "+00:00")
        datetime.fromisoformat(normalized)
        return True
    except Exception:
        return False


def _normalize_email(email) -> Optional[str]:
    if email is None:
        return None
    value = str(email).strip().lower()
    return value or None


def _normalize_phone(phone) -> Optional[str]:
    if phone is None:
        return None
    raw = str(phone).strip()
    if not raw:
        return None

    raw = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if raw.startswith("00"):
        raw = f"+{raw[2:]}"

    if not E164_PHONE_RE.fullmatch(raw):
        return None
    return raw


def _normalize_name(name) -> str:
    return " ".join(str(name or "").strip().split())


def _normalize_name_key(name) -> Optional[str]:
    cleaned = _normalize_name(name).lower()
    return cleaned or None


def _contact_match_key(*, email: Optional[str], phone: Optional[str], name: Optional[str]) -> Optional[str]:
    if email:
        return f"email:{email}"
    if phone:
        return f"phone:{phone}"
    name_key = _normalize_name_key(name)
    if name_key:
        return f"name:{name_key}"
    return None


def _safe_parse_datetime(raw_value) -> Optional[datetime]:
    if not _is_valid_datetime(raw_value):
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _load_clean_appointments(client_id: str, desc: bool = True) -> list[dict]:
    response = (
        supabase.table("appointments")
        .select(
            "id, user_name, user_email, user_phone, "
            "scheduled_time, appointment_type, internal_notes, channel, status, created_at, recipient_language, recipient_locale"
        )
        .eq("client_id", client_id)
        .order("scheduled_time", desc=desc)
        .execute()
    )

    rows = response.data or []
    clean_rows = []
    for row in rows:
        scheduled_time = row.get("scheduled_time") if isinstance(row, dict) else None
        if not _is_valid_datetime(scheduled_time):
            logger.warning(
                "Skipping appointment with invalid scheduled_time. id=%s",
                row.get("id") if isinstance(row, dict) else None,
            )
            continue
        clean_rows.append(row)
    return clean_rows


def _is_missing_appointment_clients_table(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "appointment_clients" in msg and (
        "does not exist" in msg or "not found" in msg or "relation" in msg or "schema cache" in msg
    )


def _is_missing_deleted_at_column(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "deleted_at" in msg and (
        "does not exist" in msg or "not found" in msg or "column" in msg or "schema cache" in msg
    )


def _serialize_directory_client(row: dict) -> dict:
    email = _normalize_email(row.get("user_email"))
    phone = _normalize_phone(row.get("user_phone"))
    return {
        "id": row.get("id"),
        "source": "directory",
        "user_name": _normalize_name(row.get("user_name")),
        "user_email": email,
        "user_phone": phone,
        "normalized_email": row.get("normalized_email") or email,
        "normalized_phone": row.get("normalized_phone") or phone,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "preferred_language": row.get("preferred_language"),
        "preferred_locale": row.get("preferred_locale"),
        "appointments_count": 0,
        "first_appointment_time": None,
        "last_appointment_time": None,
    }


def _load_directory_rows(client_id: str) -> tuple[list[dict], bool]:
    try:
        res = (
            supabase.table("appointment_clients")
            .select(
                "id, user_name, user_email, user_phone, normalized_email, normalized_phone, "
                "preferred_language, preferred_locale, created_at, updated_at, deleted_at"
            )
            .eq("client_id", client_id)
            .is_("deleted_at", None)
            .order("updated_at", desc=True)
            .execute()
        )
        return (res.data or []), True
    except Exception as exc:
        if _is_missing_appointment_clients_table(exc):
            logger.warning("appointment_clients table unavailable; falling back to appointments-derived contacts")
            return [], False
        if _is_missing_deleted_at_column(exc):
            # Backward compatibility before soft-delete migration is applied.
            legacy_res = (
                supabase.table("appointment_clients")
                .select(
                    "id, user_name, user_email, user_phone, normalized_email, normalized_phone, "
                    "preferred_language, preferred_locale, created_at, updated_at"
                )
                .eq("client_id", client_id)
                .order("updated_at", desc=True)
                .execute()
            )
            return (legacy_res.data or []), True
        raise


def _build_clients_list(client_id: str, q: Optional[str]) -> dict:
    appointments = _load_clean_appointments(client_id, desc=True)
    directory_rows, directory_available = _load_directory_rows(client_id)

    merged: dict[str, dict] = {}

    for row in directory_rows:
        entry = _serialize_directory_client(row)
        match_key = _contact_match_key(
            email=entry.get("normalized_email"),
            phone=entry.get("normalized_phone"),
            name=entry.get("user_name"),
        )
        if not match_key:
            continue
        entry["match_key"] = match_key
        merged[match_key] = entry

    for appt in appointments:
        email = _normalize_email(appt.get("user_email"))
        phone = _normalize_phone(appt.get("user_phone"))
        name = _normalize_name(appt.get("user_name"))
        match_key = _contact_match_key(email=email, phone=phone, name=name)
        if not match_key:
            continue

        entry = merged.get(match_key)
        if not entry:
            entry = {
                "id": None,
                "source": "appointments",
                "user_name": name,
                "user_email": email,
                "user_phone": phone,
                "normalized_email": email,
                "normalized_phone": phone,
                "created_at": appt.get("created_at"),
                "updated_at": appt.get("created_at"),
                "preferred_language": appt.get("recipient_language"),
                "preferred_locale": appt.get("recipient_locale"),
                "appointments_count": 0,
                "first_appointment_time": None,
                "last_appointment_time": None,
                "match_key": match_key,
            }
            merged[match_key] = entry

        if not entry.get("user_name") and name:
            entry["user_name"] = name
        if not entry.get("user_email") and email:
            entry["user_email"] = email
        if not entry.get("user_phone") and phone:
            entry["user_phone"] = phone
        if not entry.get("preferred_language") and appt.get("recipient_language"):
            entry["preferred_language"] = appt.get("recipient_language")
        if not entry.get("preferred_locale") and appt.get("recipient_locale"):
            entry["preferred_locale"] = appt.get("recipient_locale")

        entry["appointments_count"] = int(entry.get("appointments_count") or 0) + 1

        scheduled_time = appt.get("scheduled_time")
        scheduled_dt = _safe_parse_datetime(scheduled_time)
        if not scheduled_dt:
            continue

        current_first = _safe_parse_datetime(entry.get("first_appointment_time"))
        current_last = _safe_parse_datetime(entry.get("last_appointment_time"))
        if current_first is None or scheduled_dt < current_first:
            entry["first_appointment_time"] = scheduled_time
        if current_last is None or scheduled_dt > current_last:
            entry["last_appointment_time"] = scheduled_time

    items = list(merged.values())
    query = (q or "").strip().lower()
    if query:
        items = [
            item
            for item in items
            if query in str(item.get("user_name") or "").lower()
            or query in str(item.get("user_email") or "").lower()
            or query in str(item.get("user_phone") or "").lower()
        ]

    def _sort_key(item: dict):
        last_dt = _safe_parse_datetime(item.get("last_appointment_time"))
        updated_dt = _safe_parse_datetime(item.get("updated_at")) or _safe_parse_datetime(item.get("created_at"))
        return (
            last_dt or datetime.min.replace(tzinfo=timezone.utc),
            updated_dt or datetime.min.replace(tzinfo=timezone.utc),
            str(item.get("user_name") or "").lower(),
        )

    items.sort(key=_sort_key, reverse=True)
    return {"clients": items, "directory_available": directory_available}


def _validate_contact_payload(payload: AppointmentClientPayload) -> dict:
    user_name = _normalize_name(payload.user_name)
    if len(user_name) < 2:
        raise HTTPException(status_code=400, detail="Client name must have at least 2 characters.")

    user_email = _normalize_email(payload.user_email)
    # Email format is already validated by EmailStr when present.
    user_phone = _normalize_phone(payload.user_phone)
    if payload.user_phone and not user_phone:
        raise HTTPException(status_code=400, detail="Phone must use international format (E.164), e.g. +525512345678.")

    if not user_email and not user_phone:
        raise HTTPException(status_code=400, detail="Provide at least email or phone.")

    if payload.preferred_language or payload.preferred_locale:
        preferred_language, preferred_locale = normalize_language_preferences(
            language_family=payload.preferred_language,
            locale_code=payload.preferred_locale,
        )
    else:
        preferred_language, preferred_locale = (None, None)
    return {
        "user_name": user_name,
        "user_email": user_email,
        "user_phone": user_phone,
        "normalized_email": user_email,
        "normalized_phone": user_phone,
        "preferred_language": preferred_language,
        "preferred_locale": preferred_locale,
    }


@router.get("/show")
def show_appointments(request: Request, client_id: UUID = Query(..., description="Client ID")):
    """
    Returns all appointments for a client (read-only).
    """
    try:
        authorize_client_request(request, str(client_id))
        return _load_clean_appointments(str(client_id), desc=True)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch appointments")
        raise HTTPException(status_code=500, detail="Unable to fetch appointments")


@router.get("/clients")
def list_appointment_clients(
    request: Request,
    client_id: UUID = Query(..., description="Client ID"),
    q: Optional[str] = Query(None, description="Search by name/email/phone"),
):
    try:
        authorize_client_request(request, str(client_id))
        return _build_clients_list(str(client_id), q)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list appointment clients")
        raise HTTPException(status_code=500, detail="Unable to fetch appointment clients")


@router.post("/clients")
def create_appointment_client(payload: AppointmentClientPayload, request: Request):
    try:
        client_id = str(payload.client_id)
        authorize_client_request(request, client_id)
        clean = _validate_contact_payload(payload)
        now_iso = datetime.now(timezone.utc).isoformat()

        existing = None
        if clean["normalized_email"]:
            res = (
                supabase.table("appointment_clients")
                .select("*")
                .eq("client_id", client_id)
                .eq("normalized_email", clean["normalized_email"])
                .limit(1)
                .execute()
            )
            existing = (res.data or [None])[0]
        if not existing and clean["normalized_phone"]:
            res = (
                supabase.table("appointment_clients")
                .select("*")
                .eq("client_id", client_id)
                .eq("normalized_phone", clean["normalized_phone"])
                .limit(1)
                .execute()
            )
            existing = (res.data or [None])[0]

        if existing:
            update_payload = {**clean, "updated_at": now_iso}
            if "deleted_at" in existing and existing.get("deleted_at") is not None:
                # Re-activate soft-deleted contact when it is created again.
                update_payload["deleted_at"] = None
            result = (
                supabase.table("appointment_clients")
                .update(update_payload)
                .eq("id", existing["id"])
                .eq("client_id", client_id)
                .execute()
            )
            row = (result.data or [None])[0]
        else:
            insert_payload = {
                "client_id": client_id,
                **clean,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            result = supabase.table("appointment_clients").insert(insert_payload).execute()
            row = (result.data or [None])[0]

        if not row:
            raise HTTPException(status_code=500, detail="Unable to save client.")
        return {"success": True, "client": _serialize_directory_client(row)}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_appointment_clients_table(exc):
            raise HTTPException(
                status_code=503,
                detail="appointment_clients table is not available yet. Run the SQL migration first.",
            )
        logger.exception("Failed to create appointment client")
        raise HTTPException(status_code=500, detail="Unable to save client")


@router.patch("/clients/{contact_id}")
def update_appointment_client(contact_id: str, payload: AppointmentClientPayload, request: Request):
    try:
        client_id = str(payload.client_id)
        authorize_client_request(request, client_id)
        clean = _validate_contact_payload(payload)

        existing_res = (
            supabase.table("appointment_clients")
            .select("*")
            .eq("id", contact_id)
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        existing_row = (existing_res.data or [None])[0]
        if not existing_row:
            raise HTTPException(status_code=404, detail="Appointment client not found.")
        if existing_row.get("deleted_at") is not None:
            raise HTTPException(status_code=404, detail="Appointment client not found.")

        result = (
            supabase.table("appointment_clients")
            .update({**clean, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", contact_id)
            .eq("client_id", client_id)
            .execute()
        )
        row = (result.data or [None])[0]
        if not row:
            raise HTTPException(status_code=404, detail="Appointment client not found.")

        return {"success": True, "client": _serialize_directory_client(row)}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_appointment_clients_table(exc):
            raise HTTPException(
                status_code=503,
                detail="appointment_clients table is not available yet. Run the SQL migration first.",
            )
        logger.exception("Failed to update appointment client")
        raise HTTPException(status_code=500, detail="Unable to update client")


@router.delete("/clients/{contact_id}")
def delete_appointment_client(
    contact_id: str,
    request: Request,
    client_id: UUID = Query(..., description="Client ID"),
):
    try:
        client_id_str = str(client_id)
        authorize_client_request(request, client_id_str)

        existing = (
            supabase.table("appointment_clients")
            .select("id, deleted_at")
            .eq("id", contact_id)
            .eq("client_id", client_id_str)
            .limit(1)
            .execute()
        )
        row = (existing.data or [None])[0]
        if not row:
            raise HTTPException(status_code=404, detail="Appointment client not found.")
        if row.get("deleted_at") is not None:
            return {"success": True, "deleted_id": contact_id, "already_deleted": True}

        now_iso = datetime.now(timezone.utc).isoformat()
        result = (
            supabase.table("appointment_clients")
            .update({"deleted_at": now_iso, "updated_at": now_iso})
            .eq("id", contact_id)
            .eq("client_id", client_id_str)
            .execute()
        )
        if not (result.data or []):
            raise HTTPException(status_code=404, detail="Appointment client not found.")
        return {"success": True, "deleted_id": contact_id}
    except HTTPException:
        raise
    except Exception as exc:
        if _is_missing_appointment_clients_table(exc):
            raise HTTPException(
                status_code=503,
                detail="appointment_clients table is not available yet. Run the SQL migration first.",
            )
        if _is_missing_deleted_at_column(exc):
            raise HTTPException(
                status_code=503,
                detail="Soft delete requires appointment_clients.deleted_at. Run the SQL migration first.",
            )
        logger.exception("Failed to delete appointment client")
        raise HTTPException(status_code=500, detail="Unable to delete client")
