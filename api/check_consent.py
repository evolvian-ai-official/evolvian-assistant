# ============================================================
# ✅ check_consent.py — Evolvian AI
# ------------------------------------------------------------
# Verifica si el consentimiento del usuario sigue vigente.
# Si al menos uno de los requerimientos está activo
# y el consentimiento está expirado o ausente, devuelve valid=False.
# ============================================================

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter()


@router.get("/check_consent")
async def check_consent(
    public_client_id: str = Query(..., description="Public client identifier")
):
    """
    Verifica si el consentimiento del usuario (widget_consents) sigue siendo válido.
    Devuelve:
      - valid: True si el consentimiento está vigente o no se requiere
      - valid: False si alguno de los requerimientos está activo y el consentimiento está vencido o ausente
    """
    try:
        # 1️⃣ Obtener client_id
        client_res = (
            supabase.table("clients")
            .select("id")
            .eq("public_client_id", public_client_id)
            .execute()
        )

        if not client_res.data:
            print(f"⚠️ Cliente no encontrado para public_client_id={public_client_id}")
            raise HTTPException(status_code=404, detail="Client not found")

        client_id = client_res.data[0]["id"]

        # 2️⃣ Obtener configuración de client_settings
        settings_res = (
            supabase.table("client_settings")
            .select(
                "require_email_consent, require_phone_consent, require_terms_consent, consent_renewal_days"
            )
            .eq("client_id", client_id)
            .execute()
        )

        # Valores por defecto
        require_email = False
        require_phone = False
        require_terms = False
        renewal_days = 90

        if settings_res.data and isinstance(settings_res.data, list) and len(settings_res.data) > 0:
            s = settings_res.data[0]
            require_email = bool(s.get("require_email_consent", False))
            require_phone = bool(s.get("require_phone_consent", False))
            require_terms = bool(s.get("require_terms_consent", False))
            renewal_days = int(s.get("consent_renewal_days") or 90)

        # 🧩 Si ningún tipo de consentimiento es requerido → válido automáticamente
        if not any([require_email, require_phone, require_terms]):
            print("ℹ️ Ningún tipo de consentimiento requerido → válido automáticamente")
            return {"valid": True, "reason": "no_requirements"}

        # 3️⃣ Buscar último consentimiento registrado
        consent_res = (
            supabase.table("widget_consents")
            .select("consent_at")
            .eq("client_id", client_id)
            .order("consent_at", desc=True)
            .limit(1)
            .execute()
        )

        # ❌ Sin registro
        if not consent_res.data or len(consent_res.data) == 0:
            print(f"⚠️ No hay consentimiento registrado para {public_client_id}")
            return {
                "valid": False,
                "reason": "no_consent_record",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        # 🧠 Validar registro
        consent_at_str = consent_res.data[0].get("consent_at")
        if not consent_at_str:
            print(f"⚠️ Registro de consentimiento inválido (sin fecha) para {public_client_id}")
            return {
                "valid": False,
                "reason": "invalid_record",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        # ⏳ Parsear fecha y calcular vencimiento
        try:
            consent_at = datetime.fromisoformat(consent_at_str.replace("Z", ""))
        except Exception:
            print(f"⚠️ Error parseando fecha {consent_at_str}")
            return {
                "valid": False,
                "reason": "invalid_date_format",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        expires_at = consent_at + timedelta(days=renewal_days)
        now = datetime.utcnow()

        # ✅ Consentimiento vigente
        if now < expires_at:
            remaining_days = (expires_at - now).days
            print(f"✅ Consentimiento vigente ({remaining_days} días restantes)")
            return {
                "valid": True,
                "reason": "active",
                "consent_at": consent_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "remaining_days": remaining_days,
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        # ❌ Consentimiento vencido (al menos uno activo)
        print(f"⚠️ Consentimiento vencido o faltante → mostrar pantalla")
        return {
            "valid": False,
            "reason": "expired",
            "consent_at": consent_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "require_email": require_email,
            "require_phone": require_phone,
            "require_terms": require_terms,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error inesperado en /check_consent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
