import os
import re
import unicodedata
import requests
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Request
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
import uuid
import logging
from postgrest.exceptions import APIError

from api.compliance.email_marketing_standard import (
    is_marketing_template_type,
    validate_marketing_template_body,
)
from api.authz import authorize_client_request, get_current_user_id
from api.config.config import supabase
from api.modules.whatsapp.template_sync import (
    build_client_template_name,
    estimate_template_pricing,
    get_client_country_code,
    get_client_template_sync_map,
    infer_template_category,
    sync_canonical_templates_for_client,
)
from api.appointments.template_language_resolution import (
    get_client_default_language_preferences,
    normalize_language_preferences,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/message_templates",
    tags=["Message Templates"]
)

BUCKET_NAME = "evolvian-documents"
MAX_FOOTER_IMAGE_BYTES = 2 * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w.\-]", "_", name)
    return name.lower()


def _load_template_with_auth(request: Request, template_id: uuid.UUID) -> dict:
    template_row = (
        supabase
        .table("message_templates")
        .select("id, client_id, channel, type")
        .eq("id", str(template_id))
        .maybe_single()
        .execute()
    )

    if not template_row.data:
        raise HTTPException(status_code=404, detail="Template not found")

    client_id = str(template_row.data.get("client_id") or "")
    if not client_id:
        raise HTTPException(status_code=404, detail="Template owner not found")

    authorize_client_request(request, client_id)
    return template_row.data


def _clear_default_for_language(
    *,
    client_id: str,
    channel: str,
    template_type: str,
    language_family: Optional[str],
    exclude_template_id: Optional[str] = None,
) -> None:
    if not language_family:
        return
    try:
        query = (
            supabase
            .table("message_templates")
            .update({"is_default_for_language": False})
            .eq("client_id", client_id)
            .eq("channel", channel)
            .eq("type", template_type)
            .eq("language_family", language_family)
            .eq("is_default_for_language", True)
        )
        if exclude_template_id:
            query = query.neq("id", exclude_template_id)
        query.execute()
    except Exception:
        logger.warning(
            "⚠️ Failed clearing existing default template for language | client_id=%s | channel=%s | type=%s | lang=%s",
            client_id,
            channel,
            template_type,
            language_family,
        )


# =====================================================
# MODELS
# =====================================================

class ReminderRule(BaseModel):
    offset_minutes: int = Field(
        ...,
        description="Minutes before appointment (negative number)"
    )
    label: Optional[str] = None




class CreateTemplatePayload(BaseModel):
    client_id: uuid.UUID
    channel: Literal["whatsapp", "email", "widget"]

    # Ahora dinámico — validado contra DB
    type: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Must exist in template_types table"
    )

    meta_template_id: Optional[uuid.UUID] = None
    body: Optional[str] = Field(
        None,
        min_length=1
    )
    label: Optional[str] = Field(
        None,
        max_length=120
    )
    language_family: Optional[str] = Field(
        None,
        description="Preferred language family for non-WhatsApp templates (es|en)"
    )
    locale_code: Optional[str] = Field(
        None,
        description="Preferred locale code for non-WhatsApp templates (e.g. es_MX, en_US)"
    )
    variant_key: Optional[str] = Field(
        "default",
        max_length=50
    )
    priority: Optional[int] = 0
    is_default_for_language: Optional[bool] = True
    frequency: Optional[List[ReminderRule]] = None
    is_active: bool = True



class UpdateTemplatePayload(BaseModel):
    label: Optional[str] = None
    body: Optional[str] = Field(None, min_length=1)
    frequency: Optional[List[ReminderRule]] = None
    language_family: Optional[str] = None
    locale_code: Optional[str] = None
    variant_key: Optional[str] = Field(None, max_length=50)
    priority: Optional[int] = None
    is_default_for_language: Optional[bool] = None
    is_active: Optional[bool] = None


# =====================================================
# FOOTER IMAGE UPLOAD
# =====================================================
@router.post("/footer_image")
async def upload_footer_image(
    request: Request,
    client_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
):
    try:
        authorize_client_request(request, str(client_id))

        content_type = (file.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image files are allowed")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(content) > MAX_FOOTER_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image too large (max 2MB)")

        supabase_url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not service_key:
            raise HTTPException(status_code=500, detail="Storage is not configured")

        safe_name = sanitize_filename(file.filename or "footer.png")
        storage_path = f"{client_id}/email_footer/{uuid.uuid4()}_{safe_name}"

        upload_url = f"{supabase_url}/storage/v1/object/{BUCKET_NAME}/{storage_path}?upsert=true"
        upload_headers = {
            "Authorization": f"Bearer {service_key}",
            "Content-Type": content_type or "application/octet-stream",
        }

        upload_res = requests.put(upload_url, headers=upload_headers, data=content, timeout=20)
        if upload_res.status_code >= 400:
            logger.error("Footer image upload failed: %s", upload_res.text)
            raise HTTPException(status_code=500, detail="Failed to upload footer image")

        signed = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            storage_path,
            expires_in=60 * 60 * 24 * 365 * 5,  # 5 years
        )
        signed_url = signed.get("signedURL") if isinstance(signed, dict) else None

        if not signed_url:
            public_url = f"{supabase_url}/storage/v1/object/public/{BUCKET_NAME}/{storage_path}"
            signed_url = public_url

        return {
            "success": True,
            "url": signed_url,
            "storage_path": storage_path,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error uploading footer image")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# CREATE TEMPLATE
# =====================================================

@router.post("")
def create_message_template(payload: CreateTemplatePayload, request: Request):
    try:
        authorize_client_request(request, str(payload.client_id))


        # =====================================================
        # 1️⃣ VALIDATE TEMPLATE TYPE (NEW — AQUÍ VA)
        # =====================================================
        type_check = (
            supabase
            .table("template_types")
            .select("id")
            .eq("id", payload.type)
            .maybe_single()
            .execute()
        )

        if not type_check.data and payload.type != "opening_message":
            raise HTTPException(
                status_code=400,
                detail="Invalid template type"
            )

        meta_template_name = None
        body = None
        language_family = None
        locale_code = None

        # --------------------------
        # WHATSAPP
        # --------------------------
        if payload.channel == "whatsapp":

            if not payload.meta_template_id:
                raise HTTPException(
                    status_code=400,
                    detail="meta_template_id is required for WhatsApp templates"
                )

            meta_template = (
                supabase
                .table("meta_approved_templates")
                .select("id, template_name, type, language")
                .eq("id", str(payload.meta_template_id))
                .eq("is_active", True)
                .single()
                .execute()
            )

            if not meta_template.data:
                raise HTTPException(
                    status_code=400,
                    detail="Meta template not found or inactive"
                )

            if meta_template.data["type"] != payload.type:
                raise HTTPException(
                    status_code=400,
                    detail="Meta template type mismatch"
                )

            canonical_template_name = meta_template.data["template_name"]
            language_family, locale_code = normalize_language_preferences(
                locale_code=meta_template.data.get("language"),
            )
            client_id_str = str(payload.client_id)
            sync_map = get_client_template_sync_map(client_id_str)
            synced_template = sync_map.get(str(payload.meta_template_id))

            if not synced_template:
                sync_canonical_templates_for_client(client_id=client_id_str)
                sync_map = get_client_template_sync_map(client_id_str)
                synced_template = sync_map.get(str(payload.meta_template_id))

            if synced_template:
                if not synced_template.get("is_active"):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Meta template is not active for this WhatsApp account. "
                            "Please wait for approval or sync again."
                        ),
                    )
                meta_template_name = (
                    synced_template.get("meta_template_name")
                    or build_client_template_name(canonical_template_name, client_id_str)
                )
            else:
                # Graceful fallback for environments that still need migration rollout.
                meta_template_name = canonical_template_name

        # --------------------------
        # EMAIL
        # --------------------------
        elif payload.channel == "email":

            if not payload.body:
                raise HTTPException(
                    status_code=400,
                    detail="body is required for email templates"
                )

            if is_marketing_template_type(payload.type):
                valid_body, missing_tokens = validate_marketing_template_body(payload.body)
                if not valid_body:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Marketing email templates must include required tokens: "
                            + ", ".join(missing_tokens)
                        ),
                    )

            body = payload.body
            default_family, _ = get_client_default_language_preferences(str(payload.client_id))
            language_family, locale_code = normalize_language_preferences(
                language_family=payload.language_family,
                locale_code=payload.locale_code,
                fallback_language=default_family,
            )

        # --------------------------
        # WIDGET
        # --------------------------
        elif payload.channel == "widget":
            if payload.type != "opening_message":
                raise HTTPException(
                    status_code=400,
                    detail="Widget templates currently support only type=opening_message",
                )
            if payload.frequency:
                raise HTTPException(
                    status_code=400,
                    detail="Widget templates do not support frequency",
                )

            if not payload.body or not str(payload.body).strip():
                raise HTTPException(
                    status_code=400,
                    detail="body is required for widget templates",
                )

            body = str(payload.body).strip()
            default_family, _ = get_client_default_language_preferences(str(payload.client_id))
            language_family, locale_code = normalize_language_preferences(
                language_family=payload.language_family,
                locale_code=payload.locale_code,
                fallback_language=default_family,
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid channel"
            )

        # --------------------------
        # Frequency validation
        # --------------------------
        if payload.frequency:
            for rule in payload.frequency:
                if rule.offset_minutes >= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="offset_minutes must be negative"
                    )

        template_data = {
            "client_id": str(payload.client_id),
            "channel": payload.channel,
            "type": payload.type,
            "meta_template_id": (
                str(payload.meta_template_id)
                if payload.channel == "whatsapp"
                else None
            ),
            "template_name": meta_template_name,  # snapshot
            "label": payload.label,
            "language_family": language_family,
            "locale_code": locale_code,
            "variant_key": (payload.variant_key or "default"),
            "priority": int(payload.priority or 0),
            "is_default_for_language": bool(
                True if payload.is_default_for_language is None else payload.is_default_for_language
            ),
            "body": body,
            "frequency": (
                [rule.dict() for rule in payload.frequency]
                if payload.frequency else None
            ),
            "is_active": payload.is_active,
        }

        if template_data.get("is_default_for_language") and template_data.get("language_family"):
            _clear_default_for_language(
                client_id=str(payload.client_id),
                channel=payload.channel,
                template_type=payload.type,
                language_family=template_data.get("language_family"),
            )

        res = (
            supabase
            .table("message_templates")
            .insert(template_data)
            .execute()
        )

        if not res.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to create message template"
            )

        return {
            "success": True,
            "template": res.data[0],
        }

    except HTTPException:
        raise
    except APIError as e:
        detail = "Internal server error"
        try:
            payload = e.args[0] if e.args else {}
            if isinstance(payload, dict):
                constraint_msg = str(payload.get("message") or "")
                if "body_required_for_email" in constraint_msg:
                    detail = (
                        "Database constraint blocks widget templates with body content. "
                        "Apply the message_templates widget-opening migration first."
                    )
                    raise HTTPException(status_code=409, detail=detail)
                if "message_templates_channel_check" in constraint_msg:
                    detail = (
                        "Database channel constraint does not allow widget templates yet. "
                        "Apply the message_templates channel migration (allow widget)."
                    )
                    raise HTTPException(status_code=409, detail=detail)
        except HTTPException:
            raise
        except Exception:
            pass
        logger.exception("Unexpected PostgREST API error creating template")
        raise HTTPException(status_code=500, detail=detail)
    except Exception:
        logger.exception("Unexpected error creating template")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/types")
def get_template_types(request: Request):
    try:
        get_current_user_id(request)

        rows = None
        try:
            res = (
                supabase
                .table("template_types")
                .select("id, description, is_active")
                .eq("is_active", True)
                .order("id")
                .execute()
            )
            rows = res.data or []
        except Exception as e_is_active:
            err_text = str(e_is_active).lower()
            if "is_active" not in err_text:
                raise
            try:
                res = (
                    supabase
                    .table("template_types")
                    .select("id, description, active")
                    .eq("active", True)
                    .order("id")
                    .execute()
                )
                rows = res.data or []
            except Exception as e_active:
                err_text_active = str(e_active).lower()
                if "active" not in err_text_active:
                    raise
                res = (
                    supabase
                    .table("template_types")
                    .select("id, description")
                    .order("id")
                    .execute()
                )
                rows = res.data or []

        cleaned_rows = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            if row.get("is_active") is False or row.get("active") is False:
                continue
            cleaned_rows.append({
                "id": row.get("id"),
                "description": row.get("description"),
            })

        return cleaned_rows

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch template types")
        raise HTTPException(status_code=500, detail="Internal server error")



# =====================================================
# UPDATE TEMPLATE
# =====================================================

@router.put("/{template_id}")
def update_message_template(
    request: Request,
    template_id: uuid.UUID,
    payload: UpdateTemplatePayload,
):
    try:

        update_data = payload.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No fields provided to update"
            )

        existing = _load_template_with_auth(request, template_id)
        channel = existing["channel"]
        template_type = existing.get("type")

        # 🔒 WhatsApp body locked
        if channel == "whatsapp" and "body" in update_data:
            raise HTTPException(
                status_code=400,
                detail="WhatsApp templates cannot update body"
            )
        if channel == "whatsapp" and (
            "language_family" in update_data or "locale_code" in update_data
        ):
            raise HTTPException(
                status_code=400,
                detail="WhatsApp template language is managed by Meta"
            )

        if channel == "email" and "body" in update_data and is_marketing_template_type(template_type):
            valid_body, missing_tokens = validate_marketing_template_body(update_data.get("body"))
            if not valid_body:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Marketing email templates must include required tokens: "
                        + ", ".join(missing_tokens)
                    ),
                )

        if channel == "widget":
            if template_type != "opening_message":
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported widget template type",
                )
            if "frequency" in update_data:
                raise HTTPException(
                    status_code=400,
                    detail="Widget templates do not support frequency",
                )
            if "body" in update_data and not str(update_data.get("body") or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="body is required for widget templates",
                )
            if "body" in update_data:
                update_data["body"] = str(update_data["body"]).strip()

        if channel in {"email", "widget"} and (
            "language_family" in update_data or "locale_code" in update_data
        ):
            default_family, _ = get_client_default_language_preferences(str(existing.get("client_id") or ""))
            normalized_family, normalized_locale = normalize_language_preferences(
                language_family=update_data.get("language_family"),
                locale_code=update_data.get("locale_code"),
                fallback_language=default_family,
            )
            update_data["language_family"] = normalized_family
            update_data["locale_code"] = normalized_locale

        if "variant_key" in update_data and update_data.get("variant_key") is None:
            update_data["variant_key"] = "default"
        if "priority" in update_data and update_data.get("priority") is None:
            update_data["priority"] = 0

        if (
            update_data.get("is_default_for_language") is True
            and channel in {"whatsapp", "email", "widget"}
        ):
            target_language_family = update_data.get("language_family")
            if not target_language_family:
                if channel == "whatsapp":
                    try:
                        meta_lookup = (
                            supabase
                            .table("meta_approved_templates")
                            .select("language")
                            .eq("id", str(existing.get("meta_template_id") or ""))
                            .limit(1)
                            .execute()
                        )
                        meta_row = (meta_lookup.data or [{}])[0]
                        target_language_family, _ = normalize_language_preferences(
                            locale_code=meta_row.get("language"),
                        )
                    except Exception:
                        target_language_family = None
                else:
                    target_language_family = existing.get("language_family")
            _clear_default_for_language(
                client_id=str(existing.get("client_id") or ""),
                channel=channel,
                template_type=str(template_type or ""),
                language_family=target_language_family,
                exclude_template_id=str(template_id),
            )

        # Frequency validation
        if "frequency" in update_data:
            if update_data["frequency"]:
                for rule in update_data["frequency"]:
                    offset = rule.get("offset_minutes")
                    if offset is None or offset >= 0:
                        raise HTTPException(
                            status_code=400,
                            detail="offset_minutes must be negative"
                        )
            else:
                update_data["frequency"] = None

        res = (
            supabase
            .table("message_templates")
            .update(update_data)
            .eq("id", str(template_id))
            .execute()
        )

        if not res.data:
            raise HTTPException(
                status_code=404,
                detail="Template not found"
            )

        return {
            "success": True,
            "template": res.data[0],
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error updating template")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# DELETE TEMPLATE (SOFT)
# =====================================================

@router.delete("/{template_id}")
def delete_message_template(template_id: uuid.UUID, request: Request):
    try:
        template_row = _load_template_with_auth(request, template_id)

        if template_row.get("channel") == "whatsapp":
            raise HTTPException(
                status_code=409,
                detail="WhatsApp templates are managed by Meta sync and cannot be deleted manually"
            )

        res = (
            supabase
            .table("message_templates")
            .update({"is_active": False})
            .eq("id", str(template_id))
            .execute()
        )

        if not res.data:
            raise HTTPException(
                status_code=404,
                detail="Template not found"
            )

        return {
            "success": True,
            "message": "Template deactivated",
            "template": res.data[0],
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error deleting template")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# GET TEMPLATES — JOIN WITH META (STABLE)
# =====================================================

@router.get("")
def get_message_templates(
    request: Request,
    client_id: uuid.UUID = Query(...),
    type: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
):
    try:
        authorize_client_request(request, str(client_id))

        query = (
            supabase
            .table("message_templates")
            .select("""
                id,
                channel,
                type,
                label,
                body,
                template_name,
                is_active,
                frequency,
                meta_template_id,
                language_family,
                locale_code,
                variant_key,
                priority,
                is_default_for_language,
                meta_approved_templates (
                    template_name,
                    parameter_count,
                    language,
                    preview_body
                )
            """)
            .eq("client_id", str(client_id))
        )

        if not include_inactive:
            query = query.eq("is_active", True)

        if type:
            query = query.eq("type", type)

        res = query.execute()

        templates = res.data or []
        client_id_str = str(client_id)
        sync_map = get_client_template_sync_map(client_id_str)
        country_code = get_client_country_code(client_id_str)

        formatted = []

        for t in templates:
            meta = t.get("meta_approved_templates")
            is_whatsapp = t.get("channel") == "whatsapp"
            meta_template_id = str(t.get("meta_template_id") or "")
            resolved_language_family = None
            resolved_locale_code = None

            if is_whatsapp and not meta_template_id:
                logger.warning(
                    "⚠️ Skipping legacy WhatsApp template without canonical meta_template_id | template_id=%s",
                    t.get("id"),
                )
                continue

            if is_whatsapp and not meta:
                logger.warning(
                    "⚠️ Skipping WhatsApp template with missing canonical meta_approved_templates row | template_id=%s | meta_template_id=%s",
                    t.get("id"),
                    meta_template_id,
                )
                continue
            if is_whatsapp and meta:
                resolved_language_family, resolved_locale_code = normalize_language_preferences(
                    locale_code=meta.get("language"),
                )
            else:
                resolved_language_family, resolved_locale_code = normalize_language_preferences(
                    language_family=t.get("language_family"),
                    locale_code=t.get("locale_code"),
                )

            sync_row = sync_map.get(meta_template_id) if meta_template_id else None

            template_category = infer_template_category(t.get("type"))
            pricing = estimate_template_pricing(
                category=sync_row.get("category") if sync_row else template_category,
                country_code=country_code,
            )
            estimated_unit_cost = (
                sync_row.get("estimated_unit_cost")
                if sync_row and sync_row.get("estimated_unit_cost") is not None
                else pricing["unit_cost_estimate"]
            )
            billable = (
                bool(sync_row.get("billable"))
                if sync_row and sync_row.get("billable") is not None
                else pricing["billable"]
            )
            pricing_currency = (
                sync_row.get("pricing_currency")
                if sync_row and sync_row.get("pricing_currency")
                else pricing["currency"]
            )
            pricing_source = (
                sync_row.get("pricing_source")
                if sync_row and sync_row.get("pricing_source")
                else pricing["pricing_source"]
            )

            formatted.append({
                "id": t["id"],
                "channel": t["channel"],
                "type": t["type"],
                "label": t.get("label"),
                "language_family": resolved_language_family,
                "locale_code": resolved_locale_code,
                "variant_key": t.get("variant_key") or "default",
                "priority": int(t.get("priority") or 0),
                "is_default_for_language": bool(
                    True if t.get("is_default_for_language") is None else t.get("is_default_for_language")
                ),
                "is_active": bool(t.get("is_active", True)),
                "body": None if is_whatsapp else t.get("body"),
                "template_name": t.get("template_name"),
                "meta_template_name": meta.get("template_name") if meta else None,
                "meta_parameter_count": meta.get("parameter_count") if meta else None,
                "meta_language": meta.get("language") if meta else None,
                "meta_preview_body": meta.get("preview_body") if meta else None,
                "frequency": t.get("frequency"),
                "needs_frequency": (
                    bool(t.get("is_active", True))
                    and str(t.get("type") or "") == "appointment_reminder"
                    and not bool(t.get("frequency"))
                ),
                "meta_template_id": t.get("meta_template_id"),
                "is_meta_template": bool(meta),
                "template_category": template_category,
                "whatsapp_client_template_name": (
                    sync_row.get("meta_template_name")
                    if sync_row
                    else (
                        build_client_template_name(
                            meta.get("template_name") if meta else (t.get("template_name") or "template"),
                            client_id_str,
                        )
                        if is_whatsapp else None
                    )
                ),
                "whatsapp_template_status": sync_row.get("status") if sync_row else ("not_synced" if is_whatsapp else None),
                "whatsapp_template_active": (
                    bool(sync_row.get("is_active"))
                    if sync_row
                    else (False if is_whatsapp else None)
                ),
                "pricing_currency": pricing_currency if is_whatsapp else None,
                "estimated_unit_cost": float(estimated_unit_cost or 0) if is_whatsapp else None,
                "billable": billable if is_whatsapp else None,
                "pricing_source": pricing_source if is_whatsapp else None,
                "pricing_disclaimer": pricing["pricing_disclaimer"] if is_whatsapp else None,
            })

        return formatted

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error fetching templates")
        raise HTTPException(status_code=500, detail="Internal server error")
