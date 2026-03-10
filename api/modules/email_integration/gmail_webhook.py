import os
import base64
import json
import asyncio
import socket
from datetime import datetime
from email.utils import parseaddr
from email.mime.text import MIMEText

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from api.compliance.email_policy import (
    begin_email_send_audit,
    complete_email_send_audit,
)
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.email_integration.gmail_oauth import get_gmail_service  # ✅ ruta corregida
from api.modules.assistant_rag.chat_email import process_chat_email_payload  # Pipeline RAG Evolvian

# ==========================================================
# 📬 Gmail Webhook — Evolvian AI (versión sin Pub/Sub, compatible con payload Evolvian o Pub/Sub)
# ==========================================================

router = APIRouter(
    prefix="/gmail_webhook",
    tags=["Gmail Listener"],
    responses={422: {"description": "Validation Error"}},
)

# ⏱️ Timeout global para evitar bloqueos
socket.setdefaulttimeout(10)
WEBHOOK_SECRET = os.getenv("GMAIL_WEBHOOK_SECRET", "")  # opcional

def _parse_payload(body: dict):
    """
    Admite 2 formatos:
    - Evolvian: {"email": "...", "historyId": "..."} o {"emailAddress": "..."}
    - Pub/Sub: {"message": {"data": base64(json({"emailAddress": "...", "historyId": "..."}))}}
    """
    email_address = None
    history_id = None

    # Formato Evolvian
    if "email" in body or "emailAddress" in body:
        email_address = body.get("email") or body.get("emailAddress")
        history_id = body.get("historyId")
        return email_address, history_id

    # Formato Pub/Sub (por compatibilidad)
    msg = body.get("message") or {}
    data = msg.get("data")
    if data:
        try:
            decoded = json.loads(base64.b64decode(data).decode("utf-8"))
            email_address = decoded.get("emailAddress") or decoded.get("email")
            history_id = decoded.get("historyId")
        except Exception:
            pass

    return email_address, history_id


@router.post("", response_model=None)
async def gmail_webhook(request: Request):
    """
    📬 Gmail Webhook (Optimizado y No Bloqueante)
    - Acknowledge inmediato (200 OK)
    - Soporta payload Evolvian (interno) y Pub/Sub (compat)
    - Procesa en background
    """
    try:
        # Seguridad opcional
        if WEBHOOK_SECRET:
            sig = request.headers.get("X-Evolvian-Signature")
            if not sig or sig != WEBHOOK_SECRET:
                raise HTTPException(status_code=401, detail="Unauthorized")

        body = await request.json()
        email_address, history_id = _parse_payload(body)
        if not email_address:
            raise HTTPException(status_code=400, detail="email/emailAddress faltante en payload")

        print(f"📩 Webhook recibido para {email_address} | historyId={history_id}")

        # ✅ responder ya y trabajar en background
        asyncio.create_task(process_gmail_message(email_address, history_id))
        return JSONResponse(status_code=200, content={"status": "accepted"})

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error procesando webhook Gmail: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# -------------------------------------------------------------
# 🔧 Procesamiento en segundo plano (Background Task real)
# -------------------------------------------------------------
async def process_gmail_message(email_address: str, history_id: str | None):
    try:
        print(f"⚙️ Iniciando procesamiento async para {email_address}")

        # 1️⃣ Buscar canal Gmail activo
        channel_resp = (
            supabase.table("channels")
            .select("id, client_id, value, provider, type, gmail_access_token, gmail_refresh_token, gmail_expiry, active, scope, token_uri")
            .eq("type", "email")
            .eq("provider", "gmail")  # ✅ importante
            .eq("value", email_address)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not channel_resp.data:
            print(f"⚠️ Canal no encontrado o inactivo: {email_address}")
            return

        channel = channel_resp.data[0]
        client_id = channel["client_id"]
        assigned_email = channel.get("value")
        print(f"✅ Canal Gmail activo: {assigned_email} | client_id={client_id}")

        # 2️⃣ Crear servicio Gmail (sin cache, con refresh interno)
        service = get_gmail_service(channel)

        # 3️⃣ Obtener el último mensaje reciente (prioriza UNREAD; si no hay, toma 1 más reciente)
        try:
            messages_resp = service.users().messages().list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=1
            ).execute()
            messages = messages_resp.get("messages", [])
            if not messages:
                messages_resp = service.users().messages().list(
                    userId="me",
                    labelIds=["INBOX"],
                    maxResults=1
                ).execute()
                messages = messages_resp.get("messages", [])
        except Exception as e:
            print(f"⚠️ Error listando mensajes Gmail: {e}")
            return

        if not messages:
            print("ℹ️ No hay mensajes nuevos o INBOX vacío.")
            return

        msg_id = messages[0]["id"]
        msg_data = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        headers = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
        from_email = parseaddr(headers.get("from", ""))[1]
        to_email = parseaddr(headers.get("to", ""))[1]
        subject = headers.get("subject", "Sin asunto")
        message_id = headers.get("message-id", "")  # header Message-Id
        thread_id = msg_data.get("threadId")
        snippet = msg_data.get("snippet", "")
        labels = msg_data.get("labelIds", []) or []

        # Fallback de message-id (evitar choque con UNIQUE global)
        if not message_id:
            message_id = f"fallback-{msg_id}"

        print(f"✉️ Nuevo correo de {from_email} | Asunto: {subject}")

        # 4️⃣ Detección de duplicados
        try:
            existing = supabase.table("gmail_processed").select("id").eq("message_id", message_id).execute()
            if existing.data:
                print(f"⚠️ Duplicado detectado ({message_id}), se omite.")
                return
        except Exception as e:
            print(f"⚠️ Error verificando duplicados gmail_processed: {e}")

        # 5️⃣ Filtros básicos
        blocked_keywords = [
            "no-reply", "noreply", "mailer-daemon", "newsletter", "bounce",
            "alert@", "salesforce", "marketing", "crm", "ads@", "updates@"
        ]
        if from_email and any(kw in from_email.lower() for kw in blocked_keywords):
            print(f"🚫 Ignorado remitente automático: {from_email}")
            return

        if to_email and assigned_email and to_email.lower() != assigned_email.lower():
            print(f"🚫 Ignorado: destinatario incorrecto ({to_email})")
            return

        if "INBOX" not in labels:
            print(f"🚫 Ignorado: fuera de INBOX ({labels})")
            return

        # 6️⃣ Detectar hilo (thread)
        try:
            threads = (
                service.users().threads().list(
                    userId="me",
                    q=f"from:{from_email} subject:\"{subject}\"",
                    maxResults=1
                ).execute().get("threads", [])
            )
            target_thread_id = threads[0]["id"] if threads else thread_id
        except Exception as e:
            print(f"⚠️ Error detectando hilo: {e}")
            target_thread_id = thread_id

        # 7️⃣ Ejecutar pipeline RAG Evolvian (con timeout)
        try:
            result = await asyncio.wait_for(
                process_chat_email_payload(
                    {
                        "from_email": email_address,
                        "subject": subject,
                        "message": snippet,
                        "provider": "gmail",
                    }
                ),
                timeout=30,
            )
            no_reply = bool(result.get("no_reply"))
            answer = str(result.get("answer") or "").strip()
            if no_reply:
                print("🤫 Respuesta automática suprimida por política de autorespuesta institucional.")
        except asyncio.TimeoutError:
            print("⏱️ chat_email excedió 30s, respuesta por defecto.")
            no_reply = False
            answer = "Gracias por tu mensaje. Pronto te responderemos."
        except Exception as e:
            print(f"⚠️ Error ejecutando chat_email: {e}")
            no_reply = False
            answer = "Gracias por tu mensaje. Pronto te responderemos."

        # 8️⃣ Construir y enviar respuesta (MIMEText + headers de hilo)
        if not no_reply and answer:
            reply = MIMEText(answer, _subtype="plain", _charset="utf-8")
            reply["To"] = from_email
            reply["From"] = assigned_email or email_address  # correo del canal
            reply["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
            reply["In-Reply-To"] = message_id
            reply["References"] = message_id

            raw_b64 = base64.urlsafe_b64encode(reply.as_bytes()).decode("utf-8")
            reply_body = {"raw": raw_b64, "threadId": target_thread_id}

            allowed, policy = begin_email_send_audit(
                client_id=client_id,
                to_email=from_email,
                purpose="transactional",
                source="gmail_webhook_auto_reply",
                source_id=message_id,
            )
            if allowed:
                try:
                    send_result = service.users().messages().send(userId="me", body=reply_body).execute()
                    complete_email_send_audit(
                        client_id=client_id,
                        policy_result=policy,
                        success=True,
                        provider_message_id=(send_result or {}).get("id")
                        if isinstance(send_result, dict)
                        else None,
                    )
                    print(f"✅ Respuesta enviada a {from_email} (hilo {target_thread_id})")
                except Exception as e:
                    complete_email_send_audit(
                        client_id=client_id,
                        policy_result=policy,
                        success=False,
                        send_error="gmail_send_exception",
                    )
                    print(f"⚠️ Error enviando respuesta Gmail: {e}")
            else:
                print(f"⛔ Respuesta bloqueada por política outbound. to={from_email} proof={policy.get('proof_id')}")
        else:
            print("ℹ️ No se envía respuesta Gmail para este mensaje.")

        # 9️⃣ Marcar como leído (si correspondía)
        try:
            if "UNREAD" in labels:
                service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]}
                ).execute()
                print(f"📬 Marcado como leído: {msg_id}")
        except Exception as e:
            print(f"⚠️ Error marcando mensaje leído: {e}")

        # 🔟 Registrar como procesado
        try:
            supabase.table("gmail_processed").insert({
                "client_id": client_id,
                "message_id": message_id,  # UNIQUE en tu schema
                "history_id": history_id,
                "from_email": from_email,
                "processed_at": datetime.utcnow().isoformat()
            }).execute()
            print(f"✅ Mensaje registrado correctamente: {message_id}")
        except Exception as e:
            print(f"⚠️ Error insertando en gmail_processed: {e}")

    except Exception as e:
        print(f"🔥 Error en proceso Gmail: {e}")
