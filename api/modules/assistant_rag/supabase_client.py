import uuid
import logging
import os
import uuid
import stripe
from datetime import datetime
from api.config.config import supabase
from supabase import create_client, Client
from typing import Optional, List
from api.security.whatsapp_token_crypto import decrypt_whatsapp_token


# Configurar Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# -------------------------------
# USERS Y CLIENTES
# -------------------------------

def get_or_create_user(auth_user_id: str, email: str) -> str:
    try:
        print(f"🔍 Buscando usuario por ID: {auth_user_id}")
        response = supabase.table("users").select("id").eq("id", auth_user_id).maybe_single().execute()

        if not response or not response.data:
            print(f"🔍 No se encontró por ID. Buscando usuario por email: {email}")
            response = supabase.table("users").select("id").eq("email", email).maybe_single().execute()

            if not response or not response.data:
                print(f"🖕 Creando nuevo usuario: {auth_user_id}")
                insert = supabase.table("users").insert({
                    "id": auth_user_id,
                    "email": email,
                    "created_at": datetime.utcnow().isoformat(),
                    "is_new_user": False
                }).execute()

                if not insert or not insert.data:
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

        if response and response.data:
            print(f"✅ Cliente encontrado: {response.data['id']}")
            return response.data["id"]

        name = email.split("@")[0]
        new_id = str(uuid.uuid4())
        print(f"🖕 Creando cliente para user_id: {user_id} con ID: {new_id}")

        insert = supabase.table("clients").insert({
            "id": new_id,
            "user_id": user_id,
            "name": name
        }).execute()

        if not insert or not insert.data:
            raise Exception("❌ Error al crear cliente")

        print(f"✅ Cliente creado con ID: {insert.data[0]['id']}")
        return insert.data[0]["id"]

    except Exception as e:
        print(f"❌ Error en get_or_create_client_id: {e}")
        raise

import requests

def get_client_id_from_public(public_id: str) -> str | None:
    try:
        print(f"🔎 Buscando client_id desde public_id: {public_id}")

        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/clients"
        headers = {
            "apikey": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY')}",
            "Accept": "application/json"
        }
        params = {
            "select": "id",
            "public_client_id": f"eq.{public_id}"
        }

        res = requests.get(url, headers=headers, params=params)
        print("📡 Supabase response:", res.status_code)

        if res.status_code == 200 and res.json():
            return res.json()[0]["id"]
        print("⚠️ No se encontró client_id con ese public_id")
        return None
    except Exception as e:
        print(f"❌ Error en get_client_id_from_public: {e}")
        return None


# -------------------------------
# HISTORIAL
# -------------------------------

def save_history(
    client_id: str,
    session_id: str,
    role: str,
    content: str,
    channel: str = "chat",
    source_type: str = "chat",
    provider: str | None = None,
    source_id: str | None = None,
    status: str = "sent",
    metadata: dict | None = None,
):
    """
    Evolvian unified history + usage tracker.
    Compatible con flujos actuales (no rompe nada).
    """

    try:
        logging.info(
            f"✪ Guardando historial | client={client_id} | role={role} | channel={channel}"
        )

        normalized_provider = (provider or "").strip().lower() or "internal"

        data = {
            "client_id": client_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "channel": channel,
            "source_type": source_type,
            "provider": normalized_provider,
            "source_id": source_id,
            "status": status,
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat(),
        }

        res = supabase.table("history").insert(data).execute()

        if not res or not getattr(res, "data", None):
            logging.error(f"❌ Error al guardar historial: {res}")
            return

        # ---------------------------------------------------------
        # 🔢 Incrementar usage SOLO si es respuesta del assistant
        # (No contamos mensajes del usuario)
        # ---------------------------------------------------------
        if role == "assistant":
            try:
                supabase.rpc(
                    "increment_usage",
                    {
                        "p_client_id": client_id,
                        "p_channel": channel,
                        "p_source_type": source_type,
                    },
                ).execute()
            except Exception as usage_error:
                logging.warning(f"⚠️ Usage increment failed: {usage_error}")

        logging.info("✅ Historial guardado correctamente")

    except Exception as e:
        logging.error(f"❌ Error en save_history: {e}")


#-----Memoria para los chats tengan coherencia        

def get_recent_messages(client_id: str, session_id: str, limit: int = 4):
    """
    Recupera los últimos mensajes de una sesión para mantener contexto conversacional.
    """
    try:
        res = supabase.table("history")\
            .select("role, content")\
            .eq("client_id", client_id)\
            .eq("session_id", session_id)\
            .order("created_at", desc=False)\
            .limit(limit)\
            .execute()

        messages = res.data or []
        logging.info(f"🧠 Recuperados {len(messages)} mensajes previos de la sesión {session_id}")
        return messages
    except Exception as e:
        logging.error(f"❌ Error al obtener historial previo: {e}")
        return []

# -------------------------------
# PLAN Y USO
# -------------------------------

def get_client_plan(client_id: str) -> str:
    try:
        print(f"✪ Buscando plan para cliente {client_id}")
        response = supabase.table("client_settings").select("plan").eq("client_id", client_id).maybe_single().execute()
        if response.data:
            return response.data["plan"]
        return "free"
    except Exception as e:
        print(f"❌ Error en get_client_plan: {e}")
        return "free"

def is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def track_usage(client_id: str, channel: str, type: str = "question", value: int = 1):
    try:
        if not is_valid_uuid(client_id):
            print(f"⚠️ ID inválido (no UUID): {client_id}")
            return

        print(f"✪ Actualizando uso para cliente {client_id}")
        usage_res = supabase.table("client_usage")\
            .select("id, value")\
            .eq("client_id", client_id)\
            .eq("type", type)\
            .eq("channel", channel)\
            .maybe_single()\
            .execute()

        now = datetime.utcnow().isoformat()

        if usage_res and usage_res.data:
            usage_id = usage_res.data["id"]
            current_value = usage_res.data.get("value", 0)
            new_value = current_value + value

            supabase.table("client_usage").update({
                "value": new_value,
                "last_used_at": now
            }).eq("id", usage_id).execute()
            print(f"🔁 Uso actualizado. Nuevo valor: {new_value}")
        else:
            supabase.table("client_usage").insert({
                "id": str(uuid.uuid4()),
                "client_id": client_id,
                "channel": channel,
                "type": type,
                "value": value,
                "last_used_at": now
            }).execute()
            print(f"🆕 Registro de uso creado con valor: {value}")

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
            .filter("type", "eq", channel_type)\
            .filter("value", "eq", value)\
            .maybe_single()\
            .execute()

        if response.data:
            return response.data["client_id"]
        return None
    except Exception as e:
        print(f"❌ Error en get_client_id_by_channel: {e}")
        return None


def link_channel_to_client(client_id: str, channel_type: str, value: str):
    try:
        print(f"✪ Vinculando canal {channel_type}: {value} para cliente {client_id}")
        response = supabase.table("channels")\
            .select("id")\
            .eq("type", channel_type)\
            .eq("value", value)\
            .maybe_single()\
            .execute()

        if response.data:
            return response.data["id"]

        insert = supabase.table("channels").insert({
            "id": str(uuid.uuid4()),
            "type": channel_type,
            "value": value,
            "client_id": client_id
        }).execute()

        return insert.data[0]["id"]

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
# WHATSAPP (Meta Cloud API)
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

        if not response or not response.data:
            raise Exception("❌ No se encontraron credenciales de WhatsApp para este cliente.")

        print("✅ Credenciales WhatsApp encontradas.")
        wa_token = decrypt_whatsapp_token(response.data.get("wa_token"))
        return {
            "wa_phone_id": response.data["wa_phone_id"],
            "wa_token": wa_token
        }

    except Exception as e:
        print(f"❌ Error en get_whatsapp_credentials: {e}")
        raise

def get_channel_by_wa_phone_id(wa_phone_id: str):
    """
    Devuelve el canal WhatsApp completo usando phone_number_id (Meta).
    NO rompe nada existente.
    """
    try:
        print(f"🔍 Buscando canal WhatsApp por wa_phone_id={wa_phone_id}")

        res = supabase.table("channels") \
            .select("*") \
            .eq("type", "whatsapp") \
            .eq("wa_phone_id", wa_phone_id) \
            .maybe_single() \
            .execute()

        if not res or not res.data:
            print("⚠️ No channel found for wa_phone_id")
            return None

        print("✅ Canal WhatsApp encontrado")
        data = dict(res.data or {})
        data["wa_token"] = decrypt_whatsapp_token(data.get("wa_token"))
        return data

    except Exception as e:
        print(f"❌ Error en get_channel_by_wa_phone_id: {e}")
        return None

# -------------------------------------------------------------------
# WhatsApp inbound deduplication
# -------------------------------------------------------------------

def is_duplicate_wa_message(wa_message_id: str) -> bool:
    """
    Returns True if this WhatsApp message ID was already processed.
    """
    try:
        res = (
            supabase
            .table("whatsapp_inbound_dedupe")
            .select("id")
            .eq("wa_message_id", wa_message_id)
            .limit(1)
            .execute()
        )

        return bool(res.data)

    except Exception as e:
        # ⚠️ Fail-safe: if DB fails, assume duplicate
        # This prevents accidental spam
        print("❌ Dedup check failed:", str(e))
        return True


def register_wa_message(
    wa_message_id: str,
    client_id: str,
    from_number: str
):
    """
    Registers a WhatsApp message ID to prevent duplicate processing.
    """
    try:
        supabase.table("whatsapp_inbound_dedupe").insert({
            "wa_message_id": wa_message_id,
            "client_id": client_id,
            "from_number": from_number,
        }).execute()

    except Exception as e:
        # ⚠️ No raise → avoid retries / crashes
        print("❌ Failed to register WA message:", str(e))


async def get_client_whatsapp_config(client_id: str):
    try:
        res = supabase.table("channels") \
            .select("phone, wa_phone_id, wa_token") \
            .eq("client_id", client_id) \
            .eq("type", "whatsapp") \
            .maybe_single() \
            .execute()

        data = dict(res.data or {}) if res and res.data else None
        if data:
            data["wa_token"] = decrypt_whatsapp_token(data.get("wa_token"))
        return data
    except Exception as e:
        print(f"❌ Failed to fetch WhatsApp config for client {client_id}: {e}")
        return None

from datetime import datetime
import stripe
from api.utils.stripe_plan_utils import get_plan_from_price_id
from api.config.config import supabase
from api.utils.calendar_plan_cleanup import disconnect_calendar_features_for_plan

# -------------------------------
# PLAN STRIPE
# -------------------------------

async def update_client_plan_by_id(client_id: str, new_plan_id: str, subscription_id: str | None = None):
    try:
        print(f"✏️ Actualizando plan para cliente {client_id} → '{new_plan_id}'")

        update_payload = {
            "plan_id": new_plan_id,
            "cancellation_requested_at": None  # limpiamos cancelaciones previas
        }

        if subscription_id:
            update_payload["subscription_id"] = subscription_id

            try:
                # 🔍 Obtener información de la suscripción en Stripe
                subscription = stripe.Subscription.retrieve(subscription_id)
                print(f"🧾 Subscription Stripe ID: {subscription.id}")

                # ✅ Stripe devuelve los timestamps aquí
                start_ts = subscription.get("current_period_start")
                end_ts = subscription.get("current_period_end")

                # ✅ Extraer price_id real y mapearlo a plan interno si aplica
                price_id = subscription["items"]["data"][0]["price"]["id"]
                plan_from_price = get_plan_from_price_id(price_id)
                if plan_from_price:
                    update_payload["plan_id"] = plan_from_price

                # ✅ Guardar fechas del ciclo
                if start_ts:
                    update_payload["subscription_start"] = datetime.utcfromtimestamp(start_ts).isoformat()
                if end_ts:
                    update_payload["subscription_end"] = datetime.utcfromtimestamp(end_ts).isoformat()

                print(f"📅 Ciclo: {update_payload.get('subscription_start')} → {update_payload.get('subscription_end')}")

            except Exception as e:
                print(f"⚠️ No se pudieron obtener fechas de Stripe: {e}")

        # 🧾 Actualizar en Supabase
        print(f"📦 Payload listo para Supabase: {update_payload}")

        response = supabase.table("client_settings")\
            .update(update_payload)\
            .eq("client_id", client_id)\
            .execute()

        if response and response.data:
            print(f"✅ Plan actualizado correctamente para {client_id}")
        else:
            print(f"⚠️ Update ejecutado pero sin data devuelta")

        disconnect_calendar_features_for_plan(
            client_id,
            base_plan_id=update_payload.get("plan_id"),
            supabase_client=supabase,
        )

    except Exception as e:
        print(f"🔥 Error en update_client_plan_by_id: {e}")


async def get_client_id_by_subscription_id(subscription_id: str) -> str | None:
    try:
        response = supabase.table("client_settings")\
            .select("client_id")\
            .eq("subscription_id", subscription_id)\
            .execute()

        data = response.data
        if data and len(data) > 0:
            return data[0]["client_id"]

        print(f"⚠️ No se encontró cliente para sub {subscription_id}")
        return None

    except Exception as e:
        print(f"❌ Error buscando client_id por subscription_id: {e}")
        return None
