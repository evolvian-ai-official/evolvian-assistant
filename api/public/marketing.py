from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import logging
import re
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api.config.config import supabase
from api.marketing_contacts_state import upsert_marketing_contact_state
from api.security.request_limiter import enforce_rate_limit, get_request_ip


router = APIRouter(prefix="/api/public/marketing", tags=["Public Marketing"])
logger = logging.getLogger(__name__)
_MEXICO_COUNTRY_ALIASES = {"mx", "mex", "mexico", "méxico"}


def _normalize_email(value: Optional[str]) -> Optional[str]:
    cleaned = str(value or "").strip().lower()
    return cleaned or None


@lru_cache(maxsize=512)
def _get_client_country_code(client_id: str) -> str:
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        return ""
    try:
        rows = (
            supabase
            .table("client_profile")
            .select("country")
            .eq("client_id", normalized_client_id)
            .limit(1)
            .execute()
        ).data or []
        if rows:
            raw_country = str((rows[0] or {}).get("country") or "").strip().lower()
            if raw_country in _MEXICO_COUNTRY_ALIASES:
                return "MX"
            if len(raw_country) == 2 and raw_country.isalpha():
                return raw_country.upper()
    except Exception:
        logger.warning("Could not resolve client country for phone normalization | client_id=%s", normalized_client_id)
    return ""


def _normalize_phone(value: Optional[str], *, client_id: Optional[str] = None) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None
    client_country = _get_client_country_code(str(client_id or "").strip()) if client_id else ""
    if len(digits) == 10 and client_country == "MX":
        digits = f"52{digits}"
    if digits.startswith("521") and len(digits) == 13:
        digits = "52" + digits[3:]
    if len(digits) == 10:
        return None
    if len(digits) < 10 or len(digits) > 15:
        return None
    return f"+{digits}"


def _normalize_recipient_key(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    decoded = unquote(raw).strip()
    if not decoded:
        return None

    if decoded.startswith("phone:"):
        raw_phone = decoded.split(":", 1)[1]
        normalized_phone = _normalize_phone(raw_phone)
        if normalized_phone:
            return f"phone:{normalized_phone}"
        digits = re.sub(r"\D", "", raw_phone)
        if digits:
            return f"phone:+{digits}"
        return None

    if decoded.startswith("email:"):
        raw_email = decoded.split(":", 1)[1]
        normalized_email = _normalize_email(raw_email)
        return f"email:{normalized_email}" if normalized_email else None

    return decoded


def _build_session_id(*, channel: str, email: Optional[str], phone: Optional[str], recipient_key: Optional[str], campaign_id: str) -> str:
    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel == "whatsapp" and phone:
        digits = re.sub(r"\D", "", phone)
        return f"whatsapp-{digits or phone}"
    if normalized_channel == "email" and email:
        return f"email-{email}"
    if phone:
        digits = re.sub(r"\D", "", phone)
        return f"whatsapp-{digits or phone}"
    if email:
        return f"email-{email}"
    token = re.sub(r"[^a-zA-Z0-9:_-]", "", str(recipient_key or "unknown"))[:80]
    return f"marketing-{campaign_id}-{token}"


def _upsert_campaign_interest_handoff(
    *,
    client_id: str,
    campaign_id: str,
    campaign_name: str,
    channel: str,
    recipient_key: Optional[str],
    recipient_name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
) -> Optional[str]:
    now_iso = datetime.now(timezone.utc).isoformat()
    session_id = _build_session_id(
        channel=channel,
        email=email,
        phone=phone,
        recipient_key=recipient_key,
        campaign_id=campaign_id,
    )

    conversation_id = None
    try:
        convo_res = (
            supabase.table("conversations")
            .select("id")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .maybe_single()
            .execute()
        )
        if convo_res and convo_res.data:
            conversation_id = convo_res.data.get("id")
            (
                supabase.table("conversations")
                .update(
                    {
                        "status": "needs_human",
                        "primary_channel": channel,
                        "contact_name": recipient_name,
                        "contact_email": email,
                        "contact_phone": phone,
                        "latest_message_at": now_iso,
                        "last_message_preview": f"Interest click from campaign: {campaign_name}"[:240],
                        "updated_at": now_iso,
                    }
                )
                .eq("id", conversation_id)
                .eq("client_id", client_id)
                .execute()
            )
        else:
            convo_insert = (
                supabase.table("conversations")
                .insert(
                    {
                        "client_id": client_id,
                        "session_id": session_id,
                        "status": "needs_human",
                        "primary_channel": channel,
                        "contact_name": recipient_name,
                        "contact_email": email,
                        "contact_phone": phone,
                        "latest_message_at": now_iso,
                        "last_message_preview": f"Interest click from campaign: {campaign_name}"[:240],
                        "updated_at": now_iso,
                    }
                )
                .execute()
            )
            if convo_insert and convo_insert.data:
                conversation_id = convo_insert.data[0].get("id")
    except Exception as conversation_error:
        logger.warning("Could not upsert conversation for campaign interest | campaign_id=%s | error=%s", campaign_id, conversation_error)

    handoff_id = None
    try:
        existing_res = (
            supabase.table("conversation_handoff_requests")
            .select("id")
            .eq("client_id", client_id)
            .eq("session_id", session_id)
            .eq("reason", "campaign_interest")
            .in_("status", ["open", "assigned", "in_progress"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        existing = (existing_res.data or [None])[0]

        metadata = {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "recipient_key": recipient_key,
            "origin": "marketing_click_redirect",
            "auto_handoff": True,
            "lifecycle_stage": "prospect",
        }
        if existing:
            handoff_id = existing.get("id")
            (
                supabase.table("conversation_handoff_requests")
                .update(
                    {
                        "conversation_id": conversation_id,
                        "channel": channel,
                        "trigger": "campaign_interest_url_click",
                        "reason": "campaign_interest",
                        "status": "open",
                        "contact_name": recipient_name,
                        "contact_email": email,
                        "contact_phone": phone,
                        "last_user_message": "Clicked campaign interest URL",
                        "updated_at": now_iso,
                        "metadata": metadata,
                    }
                )
                .eq("id", handoff_id)
                .eq("client_id", client_id)
                .execute()
            )
        else:
            insert_res = (
                supabase.table("conversation_handoff_requests")
                .insert(
                    {
                        "client_id": client_id,
                        "conversation_id": conversation_id,
                        "session_id": session_id,
                        "channel": channel,
                        "trigger": "campaign_interest_url_click",
                        "reason": "campaign_interest",
                        "status": "open",
                        "contact_name": recipient_name,
                        "contact_email": email,
                        "contact_phone": phone,
                        "accepted_terms": True,
                        "accepted_email_marketing": False,
                        "last_user_message": "Clicked campaign interest URL",
                        "updated_at": now_iso,
                        "metadata": metadata,
                    }
                )
                .execute()
            )
            if insert_res and insert_res.data:
                handoff_id = insert_res.data[0].get("id")
    except Exception as handoff_error:
        logger.warning("Could not upsert handoff from campaign click | campaign_id=%s | error=%s", campaign_id, handoff_error)
        return None

    if not handoff_id:
        return None

    try:
        existing_alert_res = (
            supabase.table("conversation_alerts")
            .select("id,status")
            .eq("client_id", client_id)
            .eq("source_handoff_request_id", handoff_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        existing_alert = (existing_alert_res.data or [None])[0] if existing_alert_res else None
        if existing_alert:
            (
                supabase.table("conversation_alerts")
                .update(
                    {
                        "conversation_id": conversation_id,
                        "status": "open",
                        "resolved_at": None,
                        "priority": "high",
                        "title": "Prospect interested in campaign",
                        "body": f"Interest URL click on campaign: {campaign_name}"[:500],
                    }
                )
                .eq("id", existing_alert.get("id"))
                .eq("client_id", client_id)
                .execute()
            )
            return handoff_id

        (
            supabase.table("conversation_alerts")
            .insert(
                {
                    "client_id": client_id,
                    "conversation_id": conversation_id,
                    "source_handoff_request_id": handoff_id,
                    "alert_type": "human_intervention",
                    "status": "open",
                    "priority": "high",
                    "title": "Prospect interested in campaign",
                    "body": f"Interest URL click on campaign: {campaign_name}"[:500],
                }
            )
            .execute()
        )
    except Exception as alert_error:
        logger.warning("Could not upsert alert from campaign click | campaign_id=%s | handoff_id=%s | error=%s", campaign_id, handoff_id, alert_error)

    return handoff_id


@router.get("/interest/click")
def marketing_interest_click(
    request: Request,
    campaign_id: str = Query(..., min_length=8),
    recipient_key: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
):
    request_ip = get_request_ip(request)
    enforce_rate_limit(
        scope="marketing_interest_click_ip",
        key=f"{campaign_id}:{request_ip}",
        limit=180,
        window_seconds=300,
    )

    campaign_res = (
        supabase.table("marketing_campaigns")
        .select("id,client_id,name,channel,cta_url,is_active")
        .eq("id", campaign_id)
        .limit(1)
        .execute()
    )
    campaign = (campaign_res.data or [None])[0]
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    target_url = str(campaign.get("cta_url") or "").strip()
    if not target_url.startswith(("https://", "http://")):
        return HTMLResponse("<html><body><h3>Thanks for your interest.</h3></body></html>", status_code=200)

    client_id = str(campaign.get("client_id") or "").strip()
    campaign_name = str(campaign.get("name") or "Campaign").strip()
    event_channel = str(channel or campaign.get("channel") or "").strip().lower() or "unknown"
    normalized_recipient_key = _normalize_recipient_key(recipient_key)

    recipient_row = None
    if normalized_recipient_key:
        try:
            recipient_res = (
                supabase.table("marketing_campaign_recipients")
                .select("recipient_key,recipient_name,email,phone")
                .eq("campaign_id", campaign_id)
                .eq("recipient_key", normalized_recipient_key)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            recipient_row = (recipient_res.data or [None])[0]
        except Exception as recipient_error:
            logger.warning("Could not load campaign recipient for click | campaign_id=%s | recipient_key=%s | error=%s", campaign_id, normalized_recipient_key, recipient_error)

    recipient_name = str((recipient_row or {}).get("recipient_name") or "").strip() or None
    recipient_email = _normalize_email((recipient_row or {}).get("email"))
    recipient_phone = _normalize_phone((recipient_row or {}).get("phone"), client_id=client_id)

    handoff_id = _upsert_campaign_interest_handoff(
        client_id=client_id,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        channel="whatsapp" if event_channel == "whatsapp" else "email",
        recipient_key=normalized_recipient_key,
        recipient_name=recipient_name,
        email=recipient_email,
        phone=recipient_phone,
    )

    upsert_marketing_contact_state(
        supabase_client=supabase,
        client_id=client_id,
        name=recipient_name,
        email=recipient_email,
        phone=recipient_phone,
        interest_status="interested",
    )

    event_metadata = {
        "channel": event_channel,
        "recipient_key": normalized_recipient_key,
        "handoff_id": handoff_id,
        "source": "public_marketing_click_redirect",
    }
    try:
        supabase.table("marketing_campaign_events").insert(
            {
                "client_id": client_id,
                "campaign_id": campaign_id,
                "recipient_key": normalized_recipient_key,
                "event_type": "interest_yes",
                "metadata": event_metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as event_error:
        logger.warning("Could not log marketing interest click event | campaign_id=%s | error=%s", campaign_id, event_error)

    return RedirectResponse(url=target_url, status_code=302)
