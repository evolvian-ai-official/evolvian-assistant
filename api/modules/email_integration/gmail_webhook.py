import base64
import json
import re
from datetime import datetime
from email.utils import parseaddr
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.modules.email_integration.gmail_oauth import get_gmail_service
from api.modules.assistant_rag.chat_email import chat_email  # pipeline RAG Evolvian

router = APIRouter(prefix="/gmail_webhook", tags=["Gmail Listener"])

@router.post("")
async def gmail_webhook(request: Request):
    """
    📬 Webhook robusto de Gmail Automation (producción)
    - Procesa correos reales y responde automáticamente con el RAG de Evolvian
    - Ignora spam, marketing, newsletters o correos automáticos
    - Mantiene el hilo (thread) correcto
    - Solo responde si el correo fue dirigido al email configurado del cliente
    """
    try:
        body = await request.json()
        message_data = body.get("message", {}).get("data")

        if not message_data:
            raise HTTPException(status_code=400, detail="Mensaje vacío")

        decoded = json.loads(base64.b64decode(message_data).decode("utf-8"))
        email_address = decoded.get("emailAddress")
        history_id = decoded.get("historyId")

        print(f"📩 Notificación Gmail para {email_address}, historyId {history_id}")

        # ------------------------------------------------------
        # 🔍 Buscar canal activo válido en Supabase
        # ------------------------------------------------------
        channel_resp = (
            supabase.table("channels")
            .select("client_id, value, provider, gmail_access_token, gmail_refresh_token, gmail_expiry, active")
            .eq("type", "email")
            .eq("value", email_address)
            .eq("active", True)
            .limit(1)
            .execute()
        )

        if not channel_resp.data or not channel_resp.data[0].get("client_id"):
            print(f"⚠️ Canal no encontrado o sin client_id para {email_address}")
            raise HTTPException(status_code=404, detail="Canal no encontrado o sin client_id")

        channel = channel_resp.data[0]
        client_id = channel["client_id"]
        assigned_email = channel.get("value")
        print(f"✅ Canal encontrado: {assigned_email} | client_id={client_id}")

        # ------------------------------------------------------
        # 🧠 Crear servicio Gmail
        # ------------------------------------------------------
        service = get_gmail_service(channel)

        # ------------------------------------------------------
        # 📬 Obtener último mensaje recibido en INBOX
        # ------------------------------------------------------
        messages_resp = service.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=1
        ).execute()

        messages = messages_resp.get("messages", [])
        if not messages:
            print("ℹ️ No hay nuevos mensajes.")
            return {"status": "no messages"}

        msg_id = messages[0]["id"]
        msg_data = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        headers = {h["name"].lower(): h["value"] for h in msg_data["payload"]["headers"]}
        from_email = parseaddr(headers.get("from", ""))[1]
        to_email = parseaddr(headers.get("to", ""))[1]
        subject = headers.get("subject", "Sin asunto")
        message_id = headers.get("message-id", "")
        thread_id = msg_data.get("threadId")
        snippet = msg_data.get("snippet", "")
        labels = msg_data.get("labelIds", [])

        print(f"✉️ Correo recibido de {from_email} | Asunto: {subject}")
        print(f"📜 Contenido detectado: {snippet[:300]}...")

        # ------------------------------------------------------
        # 🚫 Filtro 1: Remitentes automáticos / marketing / no-reply
        # ------------------------------------------------------
        blocked_senders = [
            "mailer-daemon", "postmaster", "no-reply", "noreply", "donotreply",
            "notifications", "marketing", "newsletter", "campaign", "mailer",
            "salesforce", "crm", "promo", "ads@", "updates@", "alert@", "bounce"
        ]
        if any(kw in from_email.lower() for kw in blocked_senders):
            print(f"🚫 Ignorado remitente automático: {from_email}")
            return {"status": "ignored", "reason": "automated sender"}

        # ------------------------------------------------------
        # 🚫 Filtro 2: Correo no dirigido al email configurado
        # ------------------------------------------------------
        if to_email.lower() != assigned_email.lower():
            print(f"🚫 Ignorado: correo dirigido a {to_email}, no al asignado {assigned_email}")
            return {"status": "ignored", "reason": "different recipient"}

        # ------------------------------------------------------
        # 🚫 Filtro 3: Mensajes fuera de bandeja INBOX
        # ------------------------------------------------------
        if "INBOX" not in labels:
            print(f"🚫 Ignorado: mensaje fuera de INBOX ({labels})")
            return {"status": "ignored", "reason": "not inbox"}

        # ------------------------------------------------------
        # 🚫 Filtro 4: Análisis semántico (solo consultas reales)
        # ------------------------------------------------------
        semantic_keywords = [
            # Español - Consultas comerciales o informativas
            "hola", "buenos", "quiero", "necesito", "podrías", "pregunta",
            "precio", "ayuda", "información", "info", "duda", "consulta",
            "cotización", "servicio", "plan", "planes", "suscripción",
            "paquete", "detalle", "características", "requiero", "solicito",
            "presupuesto", "quieres", "cómo funciona", "contratar", "contactar",
            # Español - Soporte técnico o atención
            "problema", "error", "soporte", "falla", "bug", "asistencia",
            "no funciona", "acceso", "login", "contraseña", "cuenta", "bloqueado",
            "iniciar sesión", "tengo un inconveniente", "no puedo entrar",
            # Inglés - Información o ventas
            "hello", "hi", "please", "help", "question", "price", "need", "support",
            "info", "request", "inquiry", "details", "issue", "problem", "thanks",
            "plans", "subscription", "pricing", "package", "features", "quote",
            "buy", "purchase", "sign up", "trial", "demo", "access", "service",
            # Inglés - Soporte o errores
            "error", "bug", "trouble", "cannot", "can't", "login", "password",
            "account", "blocked", "technical", "assistance"
        ]

        # Buscamos coincidencias en el snippet o el subject
        text_to_check = f"{subject.lower()} {snippet.lower()}"
        if not any(k in text_to_check for k in semantic_keywords):
            print(f"🧩 Ignorado: no parece una consulta humana o de soporte.")
            return {"status": "ignored", "reason": "non-human text"}

        # ------------------------------------------------------
        # 🧵 Buscar si ya existe un hilo con este remitente
        # ------------------------------------------------------
        try:
            threads_resp = service.users().threads().list(
                userId="me", q=f"from:{from_email}", maxResults=1
            ).execute()
            threads = threads_resp.get("threads", [])
            existing_thread_id = threads[0]["id"] if threads else None
        except Exception as e:
            print(f"⚠️ No se pudo obtener hilo existente: {e}")
            existing_thread_id = None

        target_thread_id = existing_thread_id or thread_id
        print(f"🧵 Usando threadId: {target_thread_id}")

        # ------------------------------------------------------
        # 🧾 Preparar subject limpio
        # ------------------------------------------------------
        clean_subject = subject.strip()
        if not clean_subject.lower().startswith("re:"):
            clean_subject = f"Re: {clean_subject}"

        # ------------------------------------------------------
        # 🤖 Ejecutar pipeline RAG
        # ------------------------------------------------------
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

        # ------------------------------------------------------
        # ✉️ Crear respuesta en el mismo hilo
        # ------------------------------------------------------
        reply_raw = (
            f"From: {email_address}\r\n"
            f"To: {from_email}\r\n"
            f"Subject: {clean_subject}\r\n"
            f"In-Reply-To: {message_id}\r\n"
            f"References: {message_id}\r\n"
            f"Content-Type: text/plain; charset='UTF-8'\r\n\r\n"
            f"{answer}"
        )

        reply_message = {
            "raw": base64.urlsafe_b64encode(reply_raw.encode("utf-8")).decode("utf-8"),
            "threadId": target_thread_id
        }

        # ------------------------------------------------------
        # 🚀 Enviar respuesta y registrar historial
        # ------------------------------------------------------
        try:
            service.users().messages().send(userId="me", body=reply_message).execute()
            print(f"✅ Respuesta enviada a {from_email} dentro del hilo {target_thread_id}")

            supabase.table("history").insert({
                "client_id": client_id,
                "question": snippet,
                "answer": answer,
                "created_at": datetime.utcnow().isoformat(),
                "channel": "email"
            }).execute()

        except Exception as e:
            print(f"⚠️ Error enviando correo o guardando historial: {e}")

        return {
            "status": "ok",
            "message": "Respuesta enviada correctamente",
            "thread_id": target_thread_id
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"🔥 Error procesando webhook Gmail: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
