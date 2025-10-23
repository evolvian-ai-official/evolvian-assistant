import base64
import json
import asyncio
from datetime import datetime
from email.utils import parseaddr
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.email_integration.gmail_oauth import get_gmail_service
from api.modules.assistant_rag.chat_email import chat_email  # Pipeline RAG Evolvian

router = APIRouter(prefix="/gmail_webhook", tags=["Gmail Listener"])


@router.post("")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    📬 Gmail Webhook (Optimizado y No Bloqueante)
    - Acknowledge inmediato (200 OK) para evitar reintentos
    - Control de duplicados y remitentes automáticos
    - Pipeline RAG ejecutado en background
    """
    try:
        body = await request.json()
        message_data = body.get("message", {}).get("data")

        if not message_data:
            raise HTTPException(status_code=400, detail="Mensaje vacío")

        decoded = json.loads(base64.b64decode(message_data).decode("utf-8"))
        email_address = decoded.get("emailAddress")
        history_id = decoded.get("historyId")
        print(f"📩 Gmail webhook recibido para {email_address}, historyId {history_id}")

        # ✅ Responder inmediatamente para evitar reintentos Gmail
        background_tasks.add_task(process_gmail_message, email_address, history_id)
        return JSONResponse(status_code=200, content={"status": "accepted"})

    except Exception as e:
        print(f"🔥 Error procesando webhook Gmail: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# -------------------------------------------------------------
# 🔧 Función de procesamiento en background
# -------------------------------------------------------------
async def process_gmail_message(email_address: str, history_id: str):
    """
    Procesa el correo en segundo plano (fuera del hilo del webhook)
    """
    try:
        # 1️⃣ Buscar canal Gmail activo
        channel_resp = (
            supabase.table("channels")
            .select("client_id, value, provider, gmail_access_token, gmail_refresh_token, gmail_expiry, active")
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
        print(f"✅ Canal encontrado: {assigned_email} | client_id={client_id}")

        # 2️⃣ Crear servicio Gmail
        service = get_gmail_service(channel)

        # 3️⃣ Obtener último mensaje no leído
        messages_resp = service.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=1
        ).execute()
        messages = messages_resp.get("messages", [])
        if not messages:
            print("ℹ️ No hay nuevos mensajes (INBOX vacío o todos leídos).")
            return

        msg_id = messages[0]["id"]
        msg_data = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        headers = {h["name"].lower(): h["value"] for h in msg_data["payload"]["headers"]}
        from_email = parseaddr(headers.get("from", ""))[1]
        to_email = parseaddr(headers.get("to", ""))[1]
        subject = headers.get("subject", "Sin asunto")
        message_id = headers.get("message-id", "")
        thread_id = msg_data.get("threadId")
        snippet = msg_data.get("snippet", "")
        labels = msg_data.get("labelIds", [])

        print(f"✉️ Correo recibido de {from_email} | Asunto: {subject}")

        # 4️⃣ Control de duplicados
        existing = supabase.table("gmail_processed").select("id").eq("message_id", message_id).execute()
        if existing.data:
            print(f"⚠️ Mensaje duplicado detectado ({message_id}), omitiendo.")
            return

        # 5️⃣ Filtros básicos (no-reply, newsletters, etc.)
        blocked_keywords = [
            "no-reply", "noreply", "mailer-daemon", "newsletter", "bounce", "alert@", "salesforce", "marketing"
        ]
        if any(kw in from_email.lower() for kw in blocked_keywords):
            print(f"🚫 Ignorado remitente automático: {from_email}")
            return
        if to_email.lower() != assigned_email.lower():
            print(f"🚫 Ignorado: destinatario no coincide ({to_email})")
            return
        if "INBOX" not in labels:
            print(f"🚫 Ignorado: fuera de INBOX {labels}")
            return

        # 6️⃣ Detectar hilo existente
        try:
            threads = (
                service.users().threads().list(
                    userId="me", q=f"from:{from_email} subject:{subject}", maxResults=1
                ).execute().get("threads", [])
            )
            target_thread_id = threads[0]["id"] if threads else thread_id
        except Exception:
            target_thread_id = thread_id

        # 7️⃣ Ejecutar pipeline RAG
        fake_request = Request(scope={"type": "http"})
        fake_request._body = json.dumps({
            "from_email": email_address,
            "subject": subject,
            "message": snippet
        }).encode("utf-8")

        try:
            result = await chat_email(fake_request)
            answer = result.get("answer", "Gracias por tu mensaje. Pronto te responderemos.")
        except Exception as e:
            print(f"⚠️ Error ejecutando pipeline RAG: {e}")
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

        service.users().messages().send(userId="me", body=reply_message).execute()
        print(f"✅ Respuesta enviada a {from_email} en hilo {target_thread_id}")

        # 9️⃣ Marcar como leído
        service.users().messages().modify(
            userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        print(f"📬 Marcado como leído: {msg_id}")

        # 🔟 Guardar historial
        supabase.table("history").insert({
            "client_id": client_id,
            "question": snippet,
            "answer": answer,
            "created_at": datetime.utcnow().isoformat(),
            "channel": "email"
        }).execute()

        # 11️⃣ Registrar mensaje procesado
        supabase.table("gmail_processed").insert({
            "client_id": client_id,
            "message_id": message_id,
            "thread_id": target_thread_id,
            "from_email": from_email,
            "subject": subject,
            "processed_at": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        print(f"✅ Mensaje procesado y guardado: {message_id}")

    except Exception as e:
        print(f"⚠️ Error procesando mensaje Gmail: {e}")
