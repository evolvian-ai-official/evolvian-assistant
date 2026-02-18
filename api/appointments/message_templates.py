import os
import re
import unicodedata
import requests
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
import uuid
import logging

from api.config.config import supabase

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
    channel: Literal["whatsapp", "email"]

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
        min_length=5
    )
    label: Optional[str] = Field(
        None,
        max_length=120
    )
    frequency: Optional[List[ReminderRule]] = None
    is_active: bool = True



class UpdateTemplatePayload(BaseModel):
    label: Optional[str] = None
    body: Optional[str] = Field(None, min_length=5)
    frequency: Optional[List[ReminderRule]] = None
    is_active: Optional[bool] = None


# =====================================================
# FOOTER IMAGE UPLOAD
# =====================================================
@router.post("/footer_image")
async def upload_footer_image(
    client_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
):
    try:
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
def create_message_template(payload: CreateTemplatePayload):
    try:


        # =====================================================
        # 1️⃣ VALIDATE TEMPLATE TYPE (NEW — AQUÍ VA)
        # =====================================================
        type_check = (
            supabase
            .table("template_types")
            .select("id")
            .eq("id", payload.type)
            .single()
            .execute()
        )

        if not type_check.data:
            raise HTTPException(
                status_code=400,
                detail="Invalid template type"
            )

        meta_template_name = None
        body = None

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
                .select("id, template_name, type")
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

            meta_template_name = meta_template.data["template_name"]

        # --------------------------
        # EMAIL
        # --------------------------
        elif payload.channel == "email":

            if not payload.body:
                raise HTTPException(
                    status_code=400,
                    detail="body is required for email templates"
                )

            body = payload.body

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
            "body": body,
            "frequency": (
                [rule.dict() for rule in payload.frequency]
                if payload.frequency else None
            ),
            "is_active": payload.is_active,
        }

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
    except Exception:
        logger.exception("Unexpected error creating template")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/types")
def get_template_types():
    try:
        res = (
            supabase
            .table("template_types")
            .select("id, description")
            .order("id")
            .execute()
        )

        return res.data or []

    except Exception:
        logger.exception("Failed to fetch template types")
        raise HTTPException(status_code=500, detail="Internal server error")



# =====================================================
# UPDATE TEMPLATE
# =====================================================

@router.put("/{template_id}")
def update_message_template(
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

        existing = (
            supabase
            .table("message_templates")
            .select("channel")
            .eq("id", str(template_id))
            .single()
            .execute()
        )

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail="Template not found"
            )

        channel = existing.data["channel"]

        # 🔒 WhatsApp body locked
        if channel == "whatsapp" and "body" in update_data:
            raise HTTPException(
                status_code=400,
                detail="WhatsApp templates cannot update body"
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
def delete_message_template(template_id: uuid.UUID):
    try:

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
    client_id: uuid.UUID = Query(...),
    type: Optional[str] = Query(None),
):
    try:

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
                frequency,
                meta_template_id,
                meta_approved_templates (
                    template_name,
                    parameter_count,
                    language,
                    preview_body
                )
            """)
            .eq("client_id", str(client_id))
            .eq("is_active", True)
        )

        if type:
            query = query.eq("type", type)

        res = query.execute()

        templates = res.data or []

        formatted = []

        for t in templates:
            meta = t.get("meta_approved_templates")

            formatted.append({
                "id": t["id"],
                "channel": t["channel"],
                "type": t["type"],
                "label": t.get("label"),
                "body": None if t["channel"] == "whatsapp" else t.get("body"),
                "template_name": t.get("template_name"),
                "meta_template_name": meta.get("template_name") if meta else None,
                "meta_parameter_count": meta.get("parameter_count") if meta else None,
                "meta_language": meta.get("language") if meta else None,
                "meta_preview_body": meta.get("preview_body") if meta else None,
                "frequency": t.get("frequency"),
                "meta_template_id": t.get("meta_template_id"),
                "is_meta_template": bool(meta),
            })

        return formatted

    except Exception:
        logger.exception("Unexpected error fetching templates")
        raise HTTPException(status_code=500, detail="Internal server error")
