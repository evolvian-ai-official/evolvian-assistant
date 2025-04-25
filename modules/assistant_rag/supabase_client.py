from supabase import create_client
from config.config import SUPABASE_URL, SUPABASE_KEY
import uuid
from datetime import datetime

# Inicializa Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# USERS Y CLIENTES
# -------------------------------

def get_or_create_user(auth_user_id: str, email: str) -> str:
    response = supabase.table("users").select("id").eq("id", auth_user_id).execute()
    if response.data:
        return response.data[0]["id"]
    else:
        insert = supabase.table("users").insert({
            "id": auth_user_id,
            "email": email
        }).execute()
        return insert.data[0]["id"]

def get_or_create_client_id(user_id: str, email: str) -> str:
    response = supabase.table("clients").select("id").eq("user_id", user_id).execute()
    if response.data:
        return response.data[0]["id"]
    else:
        name = email.split("@")[0]
        insert = supabase.table("clients").insert({
            "user_id": user_id,
            "name": name
        }).execute()
        return insert.data[0]["id"]

# -------------------------------
# CANALES
# -------------------------------

def get_client_id_by_channel(channel_type: str, value: str) -> str:
    response = supabase.table("channels")\
        .select("client_id")\
        .eq("type", channel_type)\
        .eq("value", value)\
        .limit(1)\
        .execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]['client_id']
    else:
        return None

def link_channel_to_client(client_id: str, channel_type: str, value: str):
    response = supabase.table("channels")\
        .select("id")\
        .eq("type", channel_type)\
        .eq("value", value)\
        .execute()
    
    if response.data:
        return response.data[0]["id"]
    
    insert = supabase.table("channels").insert({
        "id": str(uuid.uuid4()),
        "type": channel_type,
        "value": value,
        "client_id": client_id
    }).execute()

    return insert.data[0]["id"]

# -------------------------------
# HISTORIAL
# -------------------------------

def save_history(client_id: str, question: str, answer: str, channel: str = "chat"):
    supabase.table("history").insert({
        "client_id": client_id,
        "question": question,
        "answer": answer,
        "channel": channel
    }).execute()

# -------------------------------
# PLAN Y USO
# -------------------------------

def get_client_plan(client_id: str) -> str:
    response = supabase.table("client_settings")\
        .select("plan")\
        .eq("client_id", client_id)\
        .single()\
        .execute()
    
    return response.data["plan"] if response.data else "free"

def track_usage(client_id: str, channel: str, type: str = "question", value: int = 1):
    try:
        # Obtener valor anterior
        usage_res = supabase.table("client_usage")\
            .select("value")\
            .eq("client_id", client_id)\
            .eq("type", type)\
            .eq("channel", channel)\
            .limit(1)\
            .execute()

        current = usage_res.data[0]["value"] if usage_res.data else 0
        new_value = current + value

        # Actualizar o insertar
        supabase.table("client_usage").upsert({
            "client_id": client_id,
            "channel": channel,
            "type": type,
            "value": new_value,
            "last_used_at": datetime.utcnow().isoformat()
        }, on_conflict="client_id").execute()

    except Exception as e:
        print(f"❌ Error en track_usage: {e}")
