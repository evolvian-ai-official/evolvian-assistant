from fastapi import APIRouter, HTTPException, Request
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request

router = APIRouter(
    prefix="/register_email_channel",
    tags=["Email Automation"]
)

@router.post("")
async def register_email_channel(payload: dict, request: Request):
    client_id = payload.get("client_id")
    email = payload.get("email")
    provider = payload.get("provider", "gmail")

    print("📩 Registrando canal de email:")
    print(f"   client_id: {client_id}")
    print(f"   email: {email}")
    print(f"   provider: {provider}")

    if not client_id or not email:
        raise HTTPException(status_code=400, detail="client_id y email son obligatorios")
    authorize_client_request(request, client_id)

    # ✅ Verificar que el cliente exista y obtener plan
    client_settings_resp = (
        supabase.table("client_settings")
        .select("plan_id")
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )

    # 🧠 Manejo explícito si no existe el cliente
    if not client_settings_resp.data or len(client_settings_resp.data) == 0:
        print("⚠️ Cliente no encontrado en client_settings.")
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    plan_id = client_settings_resp.data[0]["plan_id"]
    print(f"🧾 Plan detectado: {plan_id}")

    if plan_id not in ["premium", "white_label"]:
        raise HTTPException(
            status_code=403,
            detail="Solo planes Premium o superiores pueden usar automatización de email"
        )

    # ✅ Verificar si ya existe el canal
    existing = (
        supabase.table("channels")
        .select("id")
        .eq("client_id", client_id)
        .eq("value", email)
        .eq("type", "email")
        .execute()
    )

    if existing.data and len(existing.data) > 0:
        print("ℹ️ El canal ya existía previamente.")
        return {
            "status": "exists",
            "message": f"El canal {email} ya está registrado para este cliente."
        }

    # ✅ Insertar nuevo canal
    try:
        channel = (
            supabase.table("channels")
            .insert({
                "client_id": client_id,
                "type": "email",
                "value": email,
                "provider": provider,
                "active": True
            })
            .execute()
        )

        if not channel.data:
            raise HTTPException(status_code=500, detail="Error registrando canal de email")

        print(f"✅ Canal {email} insertado correctamente")

        return {
            "status": "ok",
            "message": f"Canal {email} registrado correctamente.",
            "channel": channel.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error insertando canal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
