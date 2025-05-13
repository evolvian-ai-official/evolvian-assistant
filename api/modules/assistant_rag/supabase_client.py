from api.config.config import supabase
import uuid
from datetime import datetime

# -------------------------------
# USERS Y CLIENTES
# -------------------------------

def get_or_create_user(auth_user_id: str, email: str) -> str:
    try:
        print(f"🔍 Buscando usuario por ID: {auth_user_id}")
        response = supabase.table("users").select("id").eq("id", auth_user_id).maybe_single().execute()

        if not response or not hasattr(response, "data") or not response.data:
            print(f"🔍 No se encontró por ID. Buscando usuario por email: {email}")
            response = supabase.table("users").select("id").eq("email", email).maybe_single().execute()

            if not response or not hasattr(response, "data") or not response.data:
                print(f"🆕 Creando nuevo usuario: {auth_user_id}")
                insert = supabase.table("users").insert({
                    "id": auth_user_id,
                    "email": email,
                    "created_at": datetime.utcnow().isoformat(),
                    "is_new_user": False
                }).execute()

                if not insert or not hasattr(insert, "data") or not insert.data:
                    raise Exception(f"❌ Error al crear usuario: {insert}")
                return insert.data[0]["id"]
            else:
                print(f"✅ Usuario encontrado por email: {email}")
                return response.data["id"]
        else:
            print(f"✅ Usuario encontrado por ID: {auth_user_id}")
            return response.data["id"]

    except Exception as e:
        print(f"❌ Error en get_or_create_user: {e}")
        raise

def get_or_create_client_id(user_id: str, email: str) -> str:
    try:
        print(f"🔍 Buscando client_id para user_id: {user_id}")
        response = supabase.table("clients").select("id").eq("user_id", user_id).maybe_single().execute()

        if response and hasattr(response, "data") and response.data:
            print(f"✅ Cliente encontrado: {response.data['id']}")
            return response.data["id"]

        name = email.split("@")[0]
        new_id = str(uuid.uuid4())
        print(f"🆕 Creando cliente para user_id: {user_id} con ID: {new_id}")

        insert = supabase.table("clients").insert({
            "id": new_id,
            "user_id": user_id,
            "name": name
        }).execute()

        if not insert or not hasattr(insert, "data") or not insert.data:
            raise Exception("❌ Error al crear cliente")

        print(f"✅ Cliente creado con ID: {insert.data[0]['id']}")
        return insert.data[0]["id"]

    except Exception as e:
        print(f"❌ Error en get_or_create_client_id: {e}")
        raise

# -------------------------------
# HISTORIAL
# -------------------------------

def save_history(client_id: str, question: str, answer: str, channel: str = "chat"):
    try:
        print(f"✪ Guardando historial para cliente {client_id}")
        supabase.table("history").insert({
            "client_id": client_id,
            "question": question,
            "answer": answer,
            "channel": channel
        }).execute()
    except Exception as e:
        print(f"❌ Error al guardar historial: {e}")

# -------------------------------
# PLAN Y USO
# -------------------------------

def get_client_plan(client_id: str) -> str:
    try:
        print(f"✪ Buscando plan para cliente {client_id}")
        response = supabase.table("client_settings").select("plan").eq("client_id", client_id).maybe_single().execute()
        if response and hasattr(response, "data") and response.data:
            return response.data["plan"]
        return "free"
    except Exception as e:
        print(f"❌ Error en get_client_plan: {e}")
        return "free"

def track_usage(client_id: str, channel: str, type: str = "question", value: int = 1):
    try:
        print(f"✪ Actualizando uso para cliente {client_id}")
        usage_res = supabase.table("client_usage").select("value")\
            .eq("client_id", client_id).eq("type", type).eq("channel", channel).maybe_single().execute()

        current = usage_res.data["value"] if usage_res and hasattr(usage_res, "data") and usage_res.data else 0
        new_value = current + value

        supabase.table("client_usage").upsert({
            "client_id": client_id,
            "channel": channel,
            "type": type,
            "value": new_value,
            "last_used_at": datetime.utcnow().isoformat()
        }, on_conflict="client_id").execute()
    except Exception as e:
        print(f"❌ Error en track_usage: {e}")

# -------------------------------
# CANALES
# -------------------------------

def get_client_id_by_channel(channel_type: str, value: str) -> str:
    try:
        print(f"✪ Buscando client_id para canal {channel_type}: {value}")
        response = supabase.table("channels")\
            .select("client_id")\
            .eq("type", channel_type)\
            .eq("value", value)\
            .maybe_single()\
            .execute()

        if response and hasattr(response, "data") and response.data:
            return response.data["client_id"]
        else:
            print("⚠️ No se encontró ningún canal para ese número")
            return None

    except Exception as e:
        print(f"❌ Error en get_client_id_by_channel: {e}")
        return None

def link_channel_to_client(client_id: str, channel_type: str, value: str):
    try:
        print(f"✪ Vinculando canal {channel_type}: {value} para cliente {client_id}")
        response = supabase.table("channels").select("id")\
            .eq("type", channel_type).eq("value", value).maybe_single().execute()

        if response and hasattr(response, "data") and response.data:
            return response.data["id"]

        insert = supabase.table("channels").insert({
            "id": str(uuid.uuid4()),
            "type": channel_type,
            "value": value,
            "client_id": client_id
        }).execute()

        return insert.data[0]["id"] if insert and hasattr(insert, "data") else None
    except Exception as e:
        print(f"❌ Error en link_channel_to_client: {e}")
        return None

# -------------------------------
# DOCUMENTOS (SIGNED URL)
# -------------------------------

def list_documents_with_signed_urls(client_id: str, bucket_name: str = "evolvian-documents", limit: int = 5):
    try:
        print(f"📂 Buscando documentos para cliente {client_id}...")
        prefix = f"{client_id}/"
        response = supabase.storage.from_(bucket_name).list(path=prefix, options={
            "limit": limit,
            "sortBy": {"column": "created_at", "order": "desc"}
        })

        if not response or len(response) == 0:
            print("⚠️ No se encontraron archivos.")
            return []

        signed_documents = []
        for obj in response:
            file_path = f"{prefix}{obj['name']}"
            signed = supabase.storage.from_(bucket_name).create_signed_url(file_path, 3600)
            signed_documents.append({
                "name": obj["name"],
                "signed_url": signed.get("signedURL")
            })

        print(f"✅ Documentos encontrados: {len(signed_documents)}")
        return signed_documents

    except Exception as e:
        print(f"❌ Error en list_documents_with_signed_urls: {e}")
        return []

# -------------------------------
# WHATSAPP
# -------------------------------

def get_whatsapp_credentials(client_id: str) -> dict:
    try:
        print(f"🔐 Buscando credenciales WhatsApp para client_id={client_id}")
        response = supabase.table("channels")\
            .select("wa_phone_id, wa_token")\
            .eq("client_id", client_id)\
            .eq("type", "whatsapp")\
            .maybe_single()\
            .execute()

        if not response or not hasattr(response, "data") or not response.data:
            raise Exception("❌ No se encontraron credenciales de WhatsApp para este cliente.")

        print("✅ Credenciales WhatsApp encontradas.")
        return {
            "wa_phone_id": response.data["wa_phone_id"],
            "wa_token": response.data["wa_token"]
        }

    except Exception as e:
        print(f"❌ Error en get_whatsapp_credentials: {e}")
        raise
