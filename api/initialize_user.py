from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import random
import string
from api.modules.assistant_rag.supabase_client import (
    get_or_create_user,
    get_or_create_client_id,
    supabase,
)

router = APIRouter()

class InitUserPayload(BaseModel):
    auth_user_id: str
    email: str

def generate_unique_public_client_id(length=12):
    chars = string.ascii_lowercase + string.digits
    max_attempts = 10

    for attempt in range(max_attempts):
        candidate = ''.join(random.choice(chars) for _ in range(length))
        existing = supabase.table("clients").select("id").eq("public_client_id", candidate).maybe_single().execute()
        if not existing or not existing.data:
            print(f"🆕 public_client_id único generado en intento {attempt+1}: {candidate}")
            return candidate
        else:
            print(f"⚠️ Intento {attempt+1}: public_client_id {candidate} ya existe")
    raise Exception("❌ No se pudo generar un public_client_id único después de varios intentos.")


def log_signup_event_once(client_id: str, auth_user_id: str, email: str):
    event_key = "funnel_signup_completed"
    existing = (
        supabase.table("history")
        .select("id")
        .eq("client_id", client_id)
        .eq("source_type", "analytics_event")
        .eq("source_id", event_key)
        .limit(1)
        .execute()
    )
    if existing.data:
        return

    now = datetime.utcnow().isoformat()
    supabase.table("history").insert({
        "client_id": client_id,
        "role": "system",
        "content": "Funnel_Signup_Completed",
        "channel": "system",
        "source_type": "analytics_event",
        "provider": "internal",
        "status": "tracked",
        "source_id": event_key,
        "metadata": {
            "event_name": "Funnel_Signup_Completed",
            "event_category": "funnel",
            "event_label": "register",
            "event_value": "signup",
            "frontend_source": "clientuploader",
            "metadata": {
                "auth_user_id": auth_user_id,
                "email": email,
            },
        },
        "session_id": "__analytics__",
        "created_at": now,
    }).execute()

@router.post("/initialize_user")
def initialize_user(payload: InitUserPayload):
    try:
        print("🚀 initialize_user ejecutándose...")
        print(f"🔵 auth_user_id={payload.auth_user_id}, email={payload.email}")

        # Crear o recuperar usuario
        user_id = get_or_create_user(payload.auth_user_id, payload.email)
        print(f"✅ User ID: {user_id}")

        # Crear o recuperar cliente
        client_id = get_or_create_client_id(user_id, payload.email)
        print(f"✅ Client ID: {client_id}")

        # Revisar public_client_id
        client_response = supabase.table("clients").select("public_client_id").eq("id", client_id).maybe_single().execute()
        public_client_id = client_response.data.get("public_client_id") if client_response and client_response.data else None

        if public_client_id:
            print(f"🔎 Public client ID existente: {public_client_id}")
        else:
            print("⚠️ No existe public_client_id, generando uno nuevo...")
            public_client_id = generate_unique_public_client_id()
            supabase.table("clients").update({"public_client_id": public_client_id}).eq("id", client_id).execute()
            print(f"🆕 Public client ID generado: {public_client_id}")

        # Verificar configuración del cliente
        try:
            settings_res = supabase.table("client_settings")\
                .select("*")\
                .eq("client_id", client_id)\
                .maybe_single()\
                .execute()

            if not settings_res or settings_res.data == {}:
                print("⚠️ Configuración no encontrada, insertando plan 'free'")
                supabase.table("client_settings").insert({
                    "client_id": client_id,
                    "assistant_name": "Evolvian",
                    "language": "es",
                    "temperature": 0.7,
                    "show_powered_by": True,
                    "plan_id": "free"
                }).execute()
            else:
                current_plan = settings_res.data.get("plan_id")
                print(f"✅ Configuración encontrada: plan={current_plan}")
                if not current_plan:
                    supabase.table("client_settings").update({"plan_id": "free"}).eq("client_id", client_id).execute()

        except Exception as e:
            print(f"❌ Error verificando client_settings: {e}")
            raise HTTPException(status_code=500, detail="client_settings_error")

        # Verificar si es nuevo usuario
        user_record = supabase.table("users").select("created_at, is_new_user").eq("id", payload.auth_user_id).maybe_single().execute()
        if not user_record or not user_record.data:
            raise Exception("No se encontró el usuario en tabla 'users'")

        created_at_str = user_record.data.get("created_at")
        if not created_at_str:
            raise Exception("El campo 'created_at' está vacío")

        now = datetime.now(timezone.utc)
        created_at = datetime.fromisoformat(created_at_str).astimezone(timezone.utc)
        is_new_user = user_record.data.get("is_new_user", False)

        if now - created_at < timedelta(minutes=5):
            if not is_new_user:
                supabase.table("users").update({"is_new_user": True}).eq("id", payload.auth_user_id).execute()
            is_new_user = True

        # 📈 Evento de embudo (signup) idempotente por cliente
        try:
            log_signup_event_once(client_id, payload.auth_user_id, payload.email)
        except Exception as event_err:
            print(f"⚠️ No se pudo registrar Funnel_Signup_Completed: {event_err}")

        # Crear fila en client_usage si no existe
        usage_res = supabase.table("client_usage").select("client_id").eq("client_id", client_id).limit(1).execute()
        if not usage_res or not usage_res.data:
            supabase.table("client_usage").insert({
                "client_id": client_id,
                "messages_used": 0,
                "documents_uploaded": 0,
                "last_used_at": datetime.utcnow().isoformat()
            }).execute()
            print(f"📈 Uso inicial creado para client_id: {client_id}")

        result = {
            "user_id": user_id,
            "client_id": client_id,
            "public_client_id": public_client_id,
            "is_new_user": is_new_user
        }
        print(f"✅ initialize_user response: {result}")
        return result

    except Exception as e:
        print(f"❌ Error en /initialize_user: {e}")
        raise HTTPException(status_code=500, detail=str(e))
