# src/api/initialize_user.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import random
import string
import uuid
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

@router.post("/initialize_user")
def initialize_user(payload: InitUserPayload):
    try:
        print(f"🚀 Versión initialize_user.py cargada correctamente.")
        print(f"🔵 Inicializando usuario: auth_user_id={payload.auth_user_id}, email={payload.email}")

        # 1. Crear o encontrar usuario
        user_id = get_or_create_user(payload.auth_user_id, payload.email)
        print(f"✅ User ID obtenido o creado: {user_id}")

        # 2. Crear o encontrar cliente
        client_id = get_or_create_client_id(user_id, payload.email)
        print(f"✅ Client ID obtenido o creado: {client_id}")

        # 3. Verificar o asignar public_client_id
        client_response = supabase.table("clients").select("public_client_id").eq("id", client_id).maybe_single().execute()
        public_client_id = client_response.data.get("public_client_id") if client_response and client_response.data else None

        if public_client_id:
            print(f"🔎 Public client ID existente: {public_client_id}")
        else:
            print(f"⚠️ No existe public_client_id, generando uno nuevo...")
            public_client_id = generate_unique_public_client_id()
            supabase.table("clients").update({"public_client_id": public_client_id}).eq("id", client_id).execute()
            verify = supabase.table("clients").select("public_client_id").eq("id", client_id).maybe_single().execute()
            if not verify or not verify.data or verify.data.get("public_client_id") != public_client_id:
                raise Exception("❌ No se pudo guardar el public_client_id en la base de datos.")
            print(f"🆕 Public client ID generado y guardado: {public_client_id}")

        # 4. Verificar o crear configuración inicial del cliente + asignar plan 'free'
        print(f"🔎 Verificando configuración del cliente {client_id}")
        settings_res = supabase.table("client_settings").select("client_id, plan_id").eq("client_id", client_id).maybe_single().execute()
        print("📤 Resultado crudo de client_settings:", settings_res)

        if not settings_res or not hasattr(settings_res, "data"):
            raise Exception("❌ Supabase no devolvió data para client_settings")

        if not settings_res.data:
            print(f"⚠️ client_settings vacío. Creando nuevo registro...")
            supabase.table("client_settings").insert({
                "client_id": client_id,
                "assistant_name": "Evolvian",
                "language": "es",
                "temperature": 0.7,
                "show_powered_by": True,
                "plan_id": "free"
            }).execute()
            print(f"🛠 Configuración creada para client_id: {client_id} con plan 'free'")
        else:
            current_plan = settings_res.data.get("plan_id")
            print(f"✅ Configuración existente encontrada: plan={current_plan}")
            if not current_plan:
                supabase.table("client_settings").update({"plan_id": "free"}).eq("client_id", client_id).execute()
                print(f"🔁 Plan 'free' asignado automáticamente a client_id: {client_id}")

        # 5. Verificar o crear uso inicial
        usage_res = supabase.table("client_usage").select("client_id").eq("client_id", client_id).maybe_single().execute()
        if not usage_res or not usage_res.data:
            supabase.table("client_usage").insert({
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "channel": "chat",
                "type": "question",
                "value": 0,
                "last_used_at": datetime.utcnow().isoformat()
            }).execute()
            supabase.table("client_usage").insert({
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "channel": "chat",
                "type": "document",
                "value": 0,
                "last_used_at": datetime.utcnow().isoformat()
            }).execute()
            print(f"📈 Uso inicial creado para client_id: {client_id}")

        # 6. Calcular si es usuario nuevo
        user_record = supabase.table("users").select("created_at, is_new_user").eq("id", payload.auth_user_id).maybe_single().execute()
        if not user_record or not user_record.data:
            raise Exception("No se encontró el usuario en tabla 'users' al calcular is_new_user")

        created_at_str = user_record.data.get("created_at")
        if not created_at_str:
            raise Exception("El campo 'created_at' está vacío o inválido")

        now = datetime.now(timezone.utc)
        created_at = datetime.fromisoformat(created_at_str).astimezone(timezone.utc)
        is_new_user = user_record.data.get("is_new_user", False)

        if now - created_at < timedelta(minutes=5):
            if not is_new_user:
                supabase.table("users").update({"is_new_user": True}).eq("id", payload.auth_user_id).execute()
                print(f"🆕 Marcado como nuevo usuario: {payload.auth_user_id}")
            is_new_user = True

        # 7. Devolver respuesta final
        return {
            "user_id": user_id,
            "client_id": client_id,
            "public_client_id": public_client_id,
            "is_new_user": is_new_user
        }

    except Exception as e:
        print(f"❌ Error en /initialize_user:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
