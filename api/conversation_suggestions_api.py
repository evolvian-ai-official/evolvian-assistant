import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.authz import authorize_client_request
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.assistant_rag.llm import openai_chat
from api.utils.feature_access import require_client_feature


router = APIRouter()
logger = logging.getLogger(__name__)


class ConversationSuggestedReplyInput(BaseModel):
    client_id: str
    language: Optional[str] = None  # "es" | "en"
    tone: Optional[str] = "professional"


def _fallback_draft(handoff: dict, history_rows: list[dict], lang: str) -> str:
    contact = str(handoff.get("contact_name") or "").strip()
    first_name = contact.split(" ")[0] if contact else ""
    greeting_es = f"Hola {first_name}," if first_name else "Hola,"
    greeting_en = f"Hi {first_name}," if first_name else "Hi,"

    last_user_msg = ""
    for row in reversed(history_rows or []):
        if str(row.get("role") or "").lower() == "user":
            last_user_msg = str(row.get("content") or "").strip()
            break

    if str(lang).lower().startswith("en"):
        return (
            f"{greeting_en}\n\n"
            "Thanks for your message. We are reviewing your request and a team member will help you shortly.\n\n"
            + (f"We understand you asked: \"{last_user_msg}\".\n\n" if last_user_msg else "")
            + "If you can share any additional details, that will help us respond faster.\n\n"
            "Best regards,\nEvolvian Team"
        )

    return (
        f"{greeting_es}\n\n"
        "Gracias por tu mensaje. Ya estamos revisando tu solicitud y un miembro del equipo te ayudará en breve.\n\n"
        + (f"Entendemos que consultaste: \"{last_user_msg}\".\n\n" if last_user_msg else "")
        + "Si puedes compartir más detalles, nos ayudará a responderte más rápido.\n\n"
        "Saludos,\nEquipo Evolvian"
    )


@router.post("/conversation_handoff_requests/{handoff_id}/suggest_reply")
def suggest_handoff_reply(handoff_id: str, payload: ConversationSuggestedReplyInput, request: Request):
    try:
        authorize_client_request(request, payload.client_id)
        require_client_feature(payload.client_id, "handoff", required_plan_label="premium")

        handoff_res = (
            supabase.table("conversation_handoff_requests")
            .select(
                "id,client_id,conversation_id,session_id,channel,reason,trigger,contact_name,contact_email,contact_phone,"
                "last_user_message,last_ai_message,metadata,status"
            )
            .eq("id", handoff_id)
            .eq("client_id", payload.client_id)
            .maybe_single()
            .execute()
        )
        handoff = handoff_res.data if handoff_res else None
        if not handoff:
            raise HTTPException(status_code=404, detail="Handoff request not found")

        metadata = handoff.get("metadata") if isinstance(handoff.get("metadata"), dict) else {}
        lang = (
            str(payload.language or "").strip().lower()
            or str(metadata.get("language") or "").strip().lower()
            or "es"
        )
        lang = "en" if lang.startswith("en") else "es"
        tone = str(payload.tone or "professional").strip().lower()

        session_id = str(handoff.get("session_id") or "").strip()
        history_rows: list[dict] = []
        if session_id:
            try:
                history_res = (
                    supabase.table("history")
                    .select("role,content,created_at,channel")
                    .eq("client_id", payload.client_id)
                    .eq("session_id", session_id)
                    .order("created_at", desc=False)
                    .limit(30)
                    .execute()
                )
                history_rows = history_res.data or []
            except Exception as history_error:
                logger.warning("Could not load history for suggested reply handoff=%s: %s", handoff_id, history_error)

        notes_rows: list[dict] = []
        try:
            convo_id = handoff.get("conversation_id")
            if convo_id:
                notes_res = (
                    supabase.table("conversation_internal_notes")
                    .select("note,created_at")
                    .eq("client_id", payload.client_id)
                    .eq("conversation_id", convo_id)
                    .order("created_at", desc=True)
                    .limit(5)
                    .execute()
                )
                notes_rows = notes_res.data or []
        except Exception as notes_error:
            logger.warning("Could not load notes for suggested reply handoff=%s: %s", handoff_id, notes_error)

        history_preview = "\n".join(
            f"{str(row.get('role') or 'assistant').title()}: {str(row.get('content') or '').strip()}"
            for row in (history_rows[-12:] if history_rows else [])
            if str(row.get("content") or "").strip()
        )[:6000]
        notes_preview = "\n".join(
            f"- {str(row.get('note') or '').strip()}"
            for row in notes_rows
            if str(row.get("note") or "").strip()
        )[:1500]

        system_msg = (
            "You are an assistant helping a human support agent draft a reply to a customer. "
            "Write a response draft only. Do not claim actions that have not been confirmed. "
            "Keep it concise, clear, and professional. "
            f"Respond in {'Spanish' if lang == 'es' else 'English'}."
        )
        if tone == "warm":
            system_msg += " Use a warm, empathetic tone."
        else:
            system_msg += " Use a professional support tone."

        user_msg = (
            f"Channel: {handoff.get('channel') or 'unknown'}\n"
            f"Handoff reason: {handoff.get('reason') or 'unknown'}\n"
            f"Customer name: {handoff.get('contact_name') or ''}\n"
            f"Customer email: {handoff.get('contact_email') or ''}\n"
            f"Customer phone: {handoff.get('contact_phone') or ''}\n"
            f"Last user message (captured): {handoff.get('last_user_message') or ''}\n"
            f"Last AI message (captured): {handoff.get('last_ai_message') or ''}\n\n"
            "Conversation timeline:\n"
            f"{history_preview or '(none)'}\n\n"
            "Internal notes (if any):\n"
            f"{notes_preview or '(none)'}\n\n"
            "Write a suggested reply draft the human agent can send next. "
            "If more information is needed, ask for it politely."
        )

        provider = "heuristic"
        suggested_reply = _fallback_draft(handoff, history_rows, lang)
        try:
            llm_resp = openai_chat(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                model="gpt-4o-mini",
                timeout=12,
            )
            llm_text = str(llm_resp or "").strip()
            if llm_text and not llm_text.lower().startswith("error:"):
                suggested_reply = llm_text
                provider = "openai"
        except Exception as llm_error:
            logger.warning("Suggested reply generation fallback for handoff=%s: %s", handoff_id, llm_error)

        return {
            "success": True,
            "handoff_id": handoff_id,
            "language": lang,
            "provider": provider,
            "suggested_reply": suggested_reply,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating suggested reply")
        raise HTTPException(status_code=500, detail=f"Suggested reply error: {e}")
