from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from api.modules.assistant_rag.supabase_client import supabase
from datetime import datetime
import uuid
import re
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# =====================================================
# HELPERS
# =====================================================

def get_client_id_from_user(auth_user_id: str) -> str:
    """
    Secure lookup of client_id from authenticated user.
    """
    user_res = (
        supabase.table("users")
        .select("id")
        .eq("id", auth_user_id)
        .execute()
    )

    if not user_res.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    client_res = (
        supabase.table("clients")
        .select("id")
        .eq("user_id", auth_user_id)
        .execute()
    )

    if not client_res.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    return client_res.data[0]["id"]


def validate_e164(number: str) -> str:
    number = number.replace("whatsapp:", "").strip()

    if not number.startswith("+"):
        number = f"+{number}"

    if not re.match(r"^\+[1-9]\d{9,14}$", number):
        raise HTTPException(
            status_code=400,
            detail="Número inválido. Formato requerido: E.164"
        )

    return number


# =====================================================
# PAYLOADS
# =====================================================

class WhatsAppLinkPayload(BaseModel):
    auth_user_id: str
    email: EmailStr
    phone: str
    provider: str = "meta"
    wa_phone_id: str | None = None
    wa_token: str | None = None


class WhatsAppUnlinkPayload(BaseModel):
    auth_user_id: str


# =====================================================
# LINK WHATSAPP
# =====================================================

@router.post("/link_whatsapp")
def link_whatsapp(payload: WhatsAppLinkPayload):
    try:
        logger.info("🔗 Linking WhatsApp channel")

        # 1️⃣ Validate provider
        if payload.provider not in ["meta", "twilio"]:
            raise HTTPException(status_code=400, detail="Proveedor inválido")

        if payload.provider == "meta":
            if not payload.wa_phone_id or not payload.wa_token:
                raise HTTPException(
                    status_code=400,
                    detail="Meta requiere wa_phone_id y wa_token"
                )

        # 2️⃣ Secure client lookup
        client_id = get_client_id_from_user(payload.auth_user_id)

        # 3️⃣ Validate phone
        number = validate_e164(payload.phone)
        now = datetime.utcnow().isoformat()

        # 4️⃣ Deactivate any previous WhatsApp channel
        supabase.table("channels") \
            .update({
                "is_active": False,
                "archived_at": now,
                "archived_reason": "replaced_by_new_connection",
                "last_disconnected_at": now,
                "updated_at": now
            }) \
            .eq("client_id", client_id) \
            .eq("type", "whatsapp") \
            .execute()

        # 5️⃣ Insert new channel
        insert_res = supabase.table("channels") \
            .insert({
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "type": "whatsapp",
                "value": number,
                "provider": payload.provider,
                "wa_phone_id": payload.wa_phone_id,
                "wa_token": payload.wa_token,  # NEVER RETURN THIS
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "last_connected_at": now,
                "archived_at": None,
                "archived_reason": None,
                "last_disconnected_at": None
            }) \
            .execute()

        if not insert_res.data:
            raise HTTPException(status_code=500, detail="Error creando canal")

        logger.info(f"✅ WhatsApp linked for client {client_id}")

        return {
            "success": True,
            "connected": True
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("❌ link_whatsapp internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# UNLINK WHATSAPP (PRODUCTION SAFE)
# =====================================================

@router.post("/unlink_whatsapp")
def unlink_whatsapp(payload: WhatsAppUnlinkPayload):
    try:
        logger.info("🛑 Unlinking WhatsApp channel")

        client_id = get_client_id_from_user(payload.auth_user_id)
        now = datetime.utcnow().isoformat()

        update_res = supabase.table("channels") \
            .update({
                "is_active": False,
                "wa_token": None,
                "wa_phone_id": None,
                "archived_at": now,
                "archived_reason": "manual_disconnect",
                "last_disconnected_at": now,
                "updated_at": now
            }) \
            .eq("client_id", client_id) \
            .eq("type", "whatsapp") \
            .execute()

        if not update_res.data:
            logger.warning(f"⚠️ No WhatsApp channel found to unlink for client {client_id}")

        logger.info(f"✅ WhatsApp unlinked for client {client_id}")

        return {
            "success": True,
            "connected": False
        }

    except Exception:
        logger.exception("❌ unlink_whatsapp internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


# =====================================================
# STATUS (SAFE — never returns token)
# =====================================================

@router.get("/whatsapp_status")
def whatsapp_status(auth_user_id: str):
    try:
        client_id = get_client_id_from_user(auth_user_id)

        channel_res = (
            supabase.table("channels")
            .select("value, provider, wa_phone_id")
            .eq("client_id", client_id)
            .eq("type", "whatsapp")
            .eq("is_active", True)
            .execute()
        )

        if channel_res.data:
            return {
                "connected": True,
                "phone": channel_res.data[0]["value"],
                "provider": channel_res.data[0]["provider"],
                "wa_phone_id": channel_res.data[0]["wa_phone_id"]
            }

        return {"connected": False}

    except Exception:
        logger.exception("❌ whatsapp_status internal error")
        raise HTTPException(status_code=500, detail="Internal server error")
