import base64
import json
import asyncio
import socket
from datetime import datetime
from email.utils import parseaddr

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from api.modules.assistant_rag.supabase_client import supabase
from api.modules.email_integration.gmail_oauth import get_gmail_service
from api.modules.assistant_rag.chat_email import chat_email  # Pipeline RAG Evolvian

# ==========================================================
# 📬 Gmail Webhook — Evolvian AI (Versión final optimizada Render)
# ==========================================================

router = APIRouter(
    prefix="/gmail_webhook",
    tags=["Gmail Listener"],
    responses={422: {"description": "Validation Error"}},  # evita errores Pydantic
)

# ⏱️ Timeout global para evitar bloqueos en Gmail API
socket.setdefaulttimeout(10)


@router.post("", response_model=None)
async def gmail_webhook(request: Request):
    """
    📬 Gmail Webhook (Optimizado y No Bloqueante)
    - Acknowledge inmediato (200 OK) para evitar reintentos de Gmail
    - Control de duplicados, remitentes automáticos y seguridad
    - Pipeline RAG ejecutado en segundo plano con asyncio.create_task
    """
    try:
        body = await request.json()
        message_data = body.get("message", {}).get("data")

        if not message_data:
            raise HTTPException(status_code=400, detail="Mensaje vacío")

        decoded = json.loads(base64.b64decode(message_data).decode("utf-8"))
        email_address = decoded.get("emailAddress")
        history_id = decoded.get("historyId")

        if not email_address:
            raise HTTPException(status_code=400, detail="emailAddress faltante en Pub/Sub payload")

        print(f"📩 Gmail webhook recibido para {email_address} | historyId={history_id}")

        # ✅ Responder inmediatamente y procesar en background
        asyncio.create_task(process_gmail_message(email_address, history_id))
        return JSONResponse(status_code=200, content={"status": "accepted"})

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
            .select("client_id, value, gmail_access_token, gmail_refresh_token, gmail_expiry, active")
            .eq("type", "email")
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

        # 2️⃣ Crear servicio Gmail (sin cache, con timeout)
        service = get_gmail_service(channel)

        # 3️⃣ Obtener último mensaje no leído
        try:
            messages_resp = service.users().messages().list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=1
            ).execute()
        except Exception as e:
            print(f"⚠️ Error listando mensajes Gmail: {e}")
            return

        messages = messages_resp.get("messages", [])
        if not messages:
            print("ℹ️ No hay mensajes nuevos (INBOX vacío o todos leídos).")
            return

        msg_id = messages[0]["id"]
        msg_data = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        headers = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
        from_email = parseaddr(headers.get("from", ""))[1]
        to_email = parseaddr(headers.get("to", ""))[1]
        subject = headers.get("subject", "Sin asunto")
        message_id = headers.get("message-id", "")
        thread_id = msg_data.get("threadId")
        snippet = msg_data.get("snippet", "")
        labels = msg_data.get("labelIds", []) or []

        if not message_id:
            # En algunos correos raros, message-id puede faltar; genera un hash simple como fallback
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

        # 5️⃣ Filtros de remitentes automáticos y correos no válidos
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
                    q=f"from:{from_email} subject:{subject}",
                    maxResults=1
                ).execute().get("threads", [])
            )
            target_thread_id = threads[0]["id"] if threads else thread_id
        except Exception as e:
            print(f"⚠️ Error detectando hilo: {e}")
            target_thread_id = thread_id

        # 7️⃣ Ejecutar pipeline RAG Evolvian (con timeout)
        fake_request = Request(scope={"type": "http"})
        fake_request._body = json.dumps({
            "from_email": email_address,
            "subject": subject,
            "message": snippet
        }).encode("utf-8")

        try:
            result = await asyncio.wait_for(chat_email(fake_request), timeout=30)
            answer = result.get("answer", "Gracias por tu mensaje. Pronto te responderemos.")
        except asyncio.TimeoutError:
            print("⏱️ chat_email excedió 30s, respuesta por defecto.")
            answer = "Gracias por tu mensaje. Pronto te responderemos."
        except Exception as e:
            print(f"⚠️ Error ejecutando chat_email: {e}")
            answer = "Gracias por tu mensaje. Pronto te responderemos."

        # 8️⃣ Enviar respuesta
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        reply_raw = (
            f"From: {email_address}\r\n"
            f"To: {from_email}\r\n"
            f"Subject: {reply_subject}\r\n"
            f"In-Reply-To: {message_id}\r\n"
            f"References: {message_id}\r\n"
            f"Content-Type: text/plain; charset='UTF-8'\r\n\r\n"
            f"{answer}"
        )

        reply_message = {
            "raw": base64.urlsafe_b64encode(reply_raw.encode("utf-8")).decode("utf-8"),
            "threadId": target_thread_id
        }

        try:
            service.users().messages().send(userId="me", body=reply_message).execute()
            print(f"✅ Respuesta enviada a {from_email} (hilo {target_thread_id})")
        except Exception as e:
            print(f"⚠️ Error enviando respuesta Gmail: {e}")

        # 9️⃣ Marcar como leído
        try:
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            print(f"📬 Marcado como leído: {msg_id}")
        except Exception as e:
            print(f"⚠️ Error marcando mensaje leído: {e}")

        # 🔟 Guardar historial Evolvian (si tu tabla history lo soporta)
        try:
            supabase.table("history").insert({
                "client_id": client_id,
                "question": snippet,
                "answer": answer,
                "created_at": datetime.utcnow().isoformat(),
                "channel": "email"
            }).execute()
        except Exception as e:
            print(f"⚠️ Error insertando en history: {e}")

        # 11️⃣ Registrar como procesado (⚠️ NO incluir created_at si no existe en schema)
        try:
            supabase.table("gmail_processed").insert({
                "client_id": client_id,
                "message_id": message_id,
                "history_id": history_id,
                "from_email": from_email,
                "processed_at": datetime.utcnow().isoformat()
            }).execute()
            print(f"✅ Mensaje registrado correctamente: {message_id}")
        except Exception as e:
            print(f"⚠️ Error insertando en gmail_processed: {e}")

    except Exception as e:
        print(f"🔥 Error en proceso Gmail: {e}")
