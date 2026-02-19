# ============================================================
# ✅ check_consent.py — Evolvian AI
# ------------------------------------------------------------
# Verifica si el consentimiento del usuario sigue vigente.
# Si al menos uno de los requerimientos está activo
# y el consentimiento está expirado o ausente, devuelve valid=False.
# ============================================================

from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
from api.modules.assistant_rag.supabase_client import supabase
from api.security.request_limiter import enforce_rate_limit, get_request_ip

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/check_consent")
async def check_consent(
    request: Request,
    public_client_id: str = Query(..., description="Public client identifier"),
    consent_token: Optional[str] = Query(None, description="Consent token issued by /register_consent"),
    email: Optional[str] = Query(None, description="Optional email fallback lookup"),
    phone: Optional[str] = Query(None, description="Optional phone fallback lookup"),
):
    """
    Verifica si el consentimiento del usuario (widget_consents) sigue siendo válido.
    Devuelve:
      - valid: True si el consentimiento está vigente o no se requiere
      - valid: False si alguno de los requerimientos está activo y el consentimiento está vencido o ausente
    """
    try:
        request_ip = get_request_ip(request)
        enforce_rate_limit(
            scope="check_consent_ip",
            key=f"{public_client_id}:{request_ip}",
            limit=90,
            window_seconds=60,
        )

        # 1️⃣ Obtener client_id
        client_res = (
            supabase.table("clients")
            .select("id")
            .eq("public_client_id", public_client_id)
            .execute()
        )

        if not client_res.data:
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
            return {"valid": True, "reason": "no_requirements"}

        # 3️⃣ Resolver consentimiento por token (per-session/per-user)
        consent_row = None
        if consent_token:
            consent_res = (
                supabase.table("widget_consents")
                .select("id, consent_at, email, phone, accepted_terms, accepted_email_marketing")
                .eq("client_id", client_id)
                .eq("id", consent_token)
                .limit(1)
                .execute()
            )
            consent_row = (consent_res.data or [None])[0]

        # 4️⃣ Fallback legacy: email/phone si no hay token
        if not consent_row and (email or phone):
            query = (
                supabase.table("widget_consents")
                .select("id, consent_at, email, phone, accepted_terms, accepted_email_marketing")
                .eq("client_id", client_id)
                .order("consent_at", desc=True)
                .limit(1)
            )
            if email:
                query = query.eq("email", email.strip())
            if phone:
                query = query.eq("phone", phone.strip())
            fallback = query.execute()
            consent_row = (fallback.data or [None])[0]

        # ❌ Sin registro
        if not consent_row:
            return {
                "valid": False,
                "reason": "no_consent_record_for_subject",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        # 5️⃣ Validar campos requeridos explícitos
        if require_email and not (consent_row.get("email") or "").strip():
            return {
                "valid": False,
                "reason": "missing_required_email_consent",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        if require_phone and not (consent_row.get("phone") or "").strip():
            return {
                "valid": False,
                "reason": "missing_required_phone_consent",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        if require_terms and not bool(consent_row.get("accepted_terms")):
            return {
                "valid": False,
                "reason": "missing_required_terms_consent",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        # 6️⃣ Validar fecha de consentimiento
        consent_at_str = consent_row.get("consent_at")
        if not consent_at_str:
            return {
                "valid": False,
                "reason": "invalid_record",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        # ⏳ Parsear fecha y calcular vencimiento
        try:
            consent_at = datetime.fromisoformat(consent_at_str.replace("Z", "+00:00"))
            if consent_at.tzinfo is None:
                consent_at = consent_at.replace(tzinfo=timezone.utc)
        except Exception:
            return {
                "valid": False,
                "reason": "invalid_date_format",
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        expires_at = consent_at + timedelta(days=renewal_days)
        now = datetime.now(timezone.utc)

        # ✅ Consentimiento vigente
        if now < expires_at:
            remaining_days = max((expires_at - now).days, 0)
            return {
                "valid": True,
                "reason": "active",
                "consent_at": consent_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "remaining_days": remaining_days,
                "consent_token": consent_row.get("id"),
                "require_email": require_email,
                "require_phone": require_phone,
                "require_terms": require_terms,
            }

        # ❌ Consentimiento vencido (al menos uno activo)
        return {
            "valid": False,
            "reason": "expired",
            "consent_at": consent_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "consent_token": consent_row.get("id"),
            "require_email": require_email,
            "require_phone": require_phone,
            "require_terms": require_terms,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in /check_consent")
        raise HTTPException(status_code=500, detail="check_consent_failed")
