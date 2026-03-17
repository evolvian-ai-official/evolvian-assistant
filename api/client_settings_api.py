from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging
import time
import httpx
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
from api.utils.effective_plan import (
    normalize_plan_id,
    resolve_effective_plan_id,
)
from api.appointments.template_language_resolution import normalize_language_preferences

# 🧠 Prompt base por defecto
DEFAULT_PROMPT = "You are a helpful assistant. Provide relevant answers based only on the uploaded documents."

# 🎨 Fuentes permitidas (Google Fonts seguras)
ALLOWED_FONTS = ["Inter", "Roboto", "Poppins", "Open Sans"]

router = APIRouter()

_TRANSIENT_ERROR_MARKERS = (
    "server disconnected",
    "remoteprotocolerror",
    "readtimeout",
    "connection reset",
    "eof",
    "http2",
)


def _is_missing_column_error(exc: Exception, column_name: str) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg and column_name.lower() in msg


def _is_transient_network_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_ERROR_MARKERS)


def _with_retries(fn, *, attempts: int = 3, op_name: str = "supabase_call"):
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not _is_transient_network_error(exc) or attempt == attempts:
                raise
            sleep_s = 0.2 * (2 ** (attempt - 1))
            logging.warning(
                "⚠️ %s falló (%s/%s). Reintentando en %.1fs: %s",
                op_name,
                attempt,
                attempts,
                sleep_s,
                exc,
            )
            time.sleep(sleep_s)
    raise last_exc


def _run_timed(metrics: dict, key: str, fn):
    started = time.perf_counter()
    result = fn()
    metrics[key] = round((time.perf_counter() - started) * 1000, 1)
    return result


def _client_settings_select_fields(*, include_launcher_icon_url: bool = True) -> str:
    fields = [
        "client_id",
        "assistant_name",
        "language",
        "appointments_template_language",
        "temperature",
        "show_powered_by",
        "show_logo",
        "custom_prompt",
        "daily_message_limit",
        "require_email",
        "require_phone",
        "require_terms",
        "plan_id",
        "subscription_id",
        "subscription_start",
        "subscription_end",
        "cancellation_requested_at",
        "subscription_cycles",
        "created_at",
        "header_color",
        "header_text_color",
        "background_color",
        "user_message_color",
        "bot_message_color",
        "button_color",
        "button_text_color",
        "footer_text_color",
        "font_family",
        "widget_height",
        "widget_border_radius",
        "session_message_limit",
        "show_tooltip",
        "tooltip_text",
        "tooltip_bg_color",
        "tooltip_text_color",
        "show_legal_links",
        "terms_url",
        "privacy_url",
        "require_email_consent",
        "require_terms_consent",
        "consent_bg_color",
        "consent_text_color",
        "max_messages_per_session",
    ]
    if include_launcher_icon_url:
        fields.append("launcher_icon_url")
    fields.append(
        """plan:plan_id(
                    id,
                    name,
                    description,
                    max_messages,
                    max_documents,
                    is_unlimited,
                    show_powered_by,
                    supports_chat,
                    supports_email,
                    supports_whatsapp,
                    price_usd,
                    duration,
                    plan_features(feature, is_active)

                )"""
    )
    return ",\n                ".join(fields)

# ------------------------------
# MODELO DE PAYLOAD
# ------------------------------

class ClientSettingsPayload(BaseModel):
    client_id: str
    plan_id: Optional[str] = None
    assistant_name: Optional[str] = "Evolvian Assistant"
    language: Optional[str] = "es"
    appointments_template_language: Optional[str] = None
    temperature: Optional[float] = 0.7
    custom_prompt: Optional[str] = None

    show_powered_by: Optional[bool] = True
    show_logo: Optional[bool] = None
    require_email: Optional[bool] = False
    require_phone: Optional[bool] = False
    require_terms: Optional[bool] = False
    session_message_limit: Optional[int] = 24

    # 🎨 Apariencia visual del widget
    header_color: Optional[str] = None
    header_text_color: Optional[str] = None
    background_color: Optional[str] = None
    user_message_color: Optional[str] = None
    bot_message_color: Optional[str] = None
    button_color: Optional[str] = None
    button_text_color: Optional[str] = None
    footer_text_color: Optional[str] = None
    launcher_icon_url: Optional[str] = None
    font_family: Optional[str] = None
    widget_height: Optional[int] = None
    widget_border_radius: Optional[int] = None

    # 🆕 Campos nuevos del widget (legal / tooltip / consent)
    show_tooltip: Optional[bool] = False
    tooltip_text: Optional[str] = "💡 Ask me anything!"
    tooltip_bg_color: Optional[str] = "#FFF8E1"
    tooltip_text_color: Optional[str] = "#5C4B00"

    show_legal_links: Optional[bool] = False
    terms_url: Optional[str] = None
    privacy_url: Optional[str] = None

    require_email_consent: Optional[bool] = False
    require_terms_consent: Optional[bool] = False
    consent_bg_color: Optional[str] = "#FFF8E6"
    consent_text_color: Optional[str] = "#7A4F00"

    max_messages_per_session: Optional[int] = 20

    # 📆 Subscripción
    daily_message_limit: Optional[int] = None
    subscription_id: Optional[str] = None
    subscription_start: Optional[str] = None
    subscription_end: Optional[str] = None
    cancellation_requested_at: Optional[str] = None
    subscription_cycles: Optional[int] = None
    timezone: Optional[str] = None

    class Config:
        extra = "allow"  # ✅ Permite campos adicionales sin fallar


# ------------------------------
# POST /client_settings
# ------------------------------

@router.post("/client_settings")
async def upsert_client_settings(request: Request):
    """Crea o actualiza la configuración del cliente (compatible con plan_id)."""
    try:
        raw = await request.json()
        print(
            "📩 Body recibido en /client_settings (metadata):",
            {
                "keys": list(raw.keys()),
                "has_client_id": bool(raw.get("client_id")),
            },
        )

        # ⚠️ Validar client_id presente
        if not raw.get("client_id"):
            print("⚠️ Error: Falta client_id en el payload recibido.")
            raise HTTPException(status_code=400, detail="El campo 'client_id' es obligatorio.")
        authorize_client_request(request, raw["client_id"])

        # 🧹 Normalizar tipos (true/false como booleanos, números como int)
        for k, v in list(raw.items()):
            if isinstance(v, str):
                if k == "launcher_icon_url":
                    trimmed = v.strip()
                    raw[k] = trimmed or None
                    continue
                if v.lower() in ["true", "false"]:
                    raw[k] = v.lower() == "true"
                else:
                    try:
                        if "." in v:
                            raw[k] = float(v)
                        elif v.isdigit():
                            raw[k] = int(v)
                    except ValueError:
                        pass

        # 🩹 Si viene plan como objeto, convertir a plan_id
        if isinstance(raw.get("plan"), dict) and "id" in raw["plan"]:
            raw["plan_id"] = raw["plan"]["id"]
            raw.pop("plan", None)

        # 🎨 Limpieza y validación del campo font_family
        if "font_family" in raw and raw["font_family"]:
            raw["font_family"] = raw["font_family"].replace("'", "").replace('"', "").strip()
            font_name = raw["font_family"].split(",")[0].strip()
            if font_name not in ALLOWED_FONTS:
                print(f"⚠️ Fuente no permitida: {font_name}, usando Inter.")
                raw["font_family"] = "Inter, sans-serif"

        # 🧹 Eliminar campos no existentes en la tabla client_settings
        forbidden_keys = [
            "available_plans", "plan", "plan_features",
            "id", "idx", "created_at", "updated_at",
            "max_messages", "max_documents", "supports_chat",
            "supports_email", "supports_whatsapp",
            "widget_opening_template",
        ]
        for key in forbidden_keys:
            raw.pop(key, None)

        # ✅ Validar y construir el payload Pydantic
        try:
            payload = ClientSettingsPayload(**raw)
        except Exception as e:
            print(f"❌ Error al validar el payload con Pydantic: {e}")
            raise HTTPException(status_code=422, detail=f"Error de validación: {str(e)}")

        if hasattr(payload, "model_dump"):
            payload_data = payload.model_dump(exclude_unset=True)
        else:
            payload_data = payload.dict(exclude_unset=True)
        payload_dict = {k: v for k, v in payload_data.items() if v is not None}

        # 🔹 Verificar plan válido
        plan_id = payload_dict.get("plan_id")
        if plan_id:
            plan_id = normalize_plan_id(plan_id) or "free"
            plan_check = supabase.table("plans").select("id").eq("id", plan_id).single().execute()
            if not plan_check.data:
                raise HTTPException(status_code=400, detail="Plan no válido")
        else:
            current_plan_res = (
                supabase.table("client_settings")
                .select("plan_id")
                .eq("client_id", payload.client_id)
                .maybe_single()
                .execute()
            )
            plan_id = normalize_plan_id(current_plan_res.data["plan_id"]) if current_plan_res.data else "free"
        payload_dict.setdefault("plan_id", plan_id)

        effective_plan_id = resolve_effective_plan_id(
            payload.client_id,
            base_plan_id=plan_id,
            supabase_client=supabase,
        )

        # 🔒 Solo premium / white_label puede editar custom_prompt
        if effective_plan_id not in ["premium", "white_label"]:
            payload_dict.pop("custom_prompt", None)
            payload_dict.pop("launcher_icon_url", None)

        # 💾 Guardar configuración limpia
        print(
            "💾 Guardando configuración limpia (metadata):",
            {"keys": list(payload_dict.keys()), "client_id": payload.client_id},
        )
        try:
            response = supabase.table("client_settings").upsert(payload_dict, on_conflict="client_id").execute()
        except Exception as exc:
            if (
                "launcher_icon_url" in payload_dict
                and _is_missing_column_error(exc, "client_settings.launcher_icon_url")
            ):
                logging.warning(
                    "⚠️ client_settings.launcher_icon_url no existe para client_id=%s. Guardando sin esa columna.",
                    payload.client_id,
                )
                payload_dict.pop("launcher_icon_url", None)
                response = supabase.table("client_settings").upsert(payload_dict, on_conflict="client_id").execute()
            else:
                raise

        if response.data:
            print("✅ Configuración guardada correctamente para client_id:", payload.client_id)
            return JSONResponse(
                content={"message": "Configuración guardada correctamente.", "settings": response.data[0]}
            )

        raise HTTPException(status_code=500, detail="Error al guardar la configuración.")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en POST /client_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------
# GET /client_settings
# ------------------------------

@router.get("/client_settings")
def get_client_settings(
    request: Request,
    client_id: Optional[str] = Query(None),
    public_client_id: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
):
    """Obtiene la configuración del cliente."""
    request_started = time.perf_counter()
    perf_ms = {}
    try:
        if not client_id and not public_client_id:
            raise HTTPException(status_code=400, detail="Debe especificarse client_id o public_client_id")

        # Buscar client_id si llega public_client_id
        if public_client_id and not client_id:
            lookup = _run_timed(
                perf_ms,
                "public_id_lookup",
                lambda: (
                    supabase.table("clients")
                    .select("id")
                    .eq("public_client_id", public_client_id)
                    .single()
                    .execute()
                ),
            )
            if not lookup.data:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")
            client_id = lookup.data["id"]
        elif client_id:
            _run_timed(perf_ms, "authorize_client_request", lambda: authorize_client_request(request, client_id))

        # Obtener settings
        def _fetch_client_settings(include_launcher_icon_url: bool = True):
            return (
                supabase.table("client_settings")
                .select(_client_settings_select_fields(include_launcher_icon_url=include_launcher_icon_url))
                .eq("client_id", client_id)
                .single()
                .execute()
            )

        try:
            response = _run_timed(
                perf_ms,
                "settings_query",
                lambda: _with_retries(
                    lambda: _fetch_client_settings(include_launcher_icon_url=True),
                    op_name="client_settings.fetch",
                ),
            )
            client_settings_has_launcher_icon_url = True
        except Exception as settings_exc:
            if not _is_missing_column_error(settings_exc, "client_settings.launcher_icon_url"):
                raise
            logging.warning(
                "⚠️ client_settings.launcher_icon_url no existe para client_id=%s. Reintentando sin esa columna.",
                client_id,
            )
            response = _run_timed(
                perf_ms,
                "settings_query_without_launcher_icon_url",
                lambda: _with_retries(
                    lambda: _fetch_client_settings(include_launcher_icon_url=False),
                    op_name="client_settings.fetch_legacy",
                ),
            )
            client_settings_has_launcher_icon_url = False

        if not response.data:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        settings = response.data
        if not client_settings_has_launcher_icon_url:
            settings["launcher_icon_url"] = None

        # Public widget opening message template (if configured)
        widget_opening_template = None
        try:
            requested_template_language, _ = normalize_language_preferences(
                language_family=language or settings.get("language"),
            )

            def _widget_opening_template_query():
                return (
                    supabase.table("message_templates")
                    .select(
                        "id, label, body, channel, type, is_active, "
                        "language_family, locale_code, updated_at"
                    )
                    .eq("client_id", client_id)
                    .eq("channel", "widget")
                    .eq("type", "opening_message")
                    .eq("is_active", True)
                )

            def _fetch_widget_opening_template():
                base = _widget_opening_template_query()
                try:
                    return base.order("updated_at", desc=True).limit(10).execute()
                except Exception as ordered_exc:
                    lowered_error = str(ordered_exc).lower()
                    if "updated_at" not in lowered_error and "language_family" not in lowered_error and "locale_code" not in lowered_error:
                        raise
                    return (
                        supabase.table("message_templates")
                        .select("id, label, body, channel, type, is_active")
                        .eq("client_id", client_id)
                        .eq("channel", "widget")
                        .eq("type", "opening_message")
                        .eq("is_active", True)
                        .limit(10)
                        .execute()
                    )

            tpl_res = _run_timed(
                perf_ms,
                "widget_opening_template_query",
                lambda: _with_retries(
                    _fetch_widget_opening_template,
                    op_name="client_settings.widget_opening_template",
                ),
            )
            tpl_rows = tpl_res.data or []
            if tpl_rows:
                matching_rows = []
                fallback_rows = []
                for candidate in tpl_rows:
                    candidate_language = candidate.get("language_family") or candidate.get("locale_code")
                    family = None
                    if candidate_language:
                        family, _ = normalize_language_preferences(
                            language_family=candidate.get("language_family"),
                            locale_code=candidate.get("locale_code"),
                            fallback_language=requested_template_language,
                        )

                    if family == requested_template_language:
                        matching_rows.append(candidate)
                    else:
                        fallback_rows.append(candidate)

                row = (matching_rows or fallback_rows)[0]
                body = str(row.get("body") or "").strip()
                if body:
                    widget_opening_template = {
                        "id": row.get("id"),
                        "label": row.get("label"),
                        "body": body,
                        "channel": "widget",
                        "type": "opening_message",
                        "language_family": row.get("language_family") or requested_template_language,
                    }
        except Exception as tpl_err:
            logging.warning(
                "⚠️ No se pudo cargar widget opening template para client_id=%s: %s",
                client_id,
                tpl_err,
            )
        settings["widget_opening_template"] = widget_opening_template

        # Normalizar booleanos
        for key in [
            "require_email", "require_phone", "require_terms",
            "show_powered_by", "show_logo",
            "show_tooltip", "show_legal_links",
            "require_email_consent", "require_terms_consent"
        ]:
            settings[key] = bool(settings.get(key, False))

        # Fallback de plan
        plan = settings.get("plan", {})

        if not plan or not plan.get("id"):
            plan = {
                "id": "free",
                "name": "Free",
                "max_messages": 100,
                "max_documents": 3,
                "supports_chat": True,
                "supports_email": False,
                "supports_whatsapp": False,
                "price_usd": 0,
                "plan_features": []
            }

        base_plan_id = normalize_plan_id(plan.get("id") or settings.get("plan_id"))
        effective_plan_id = resolve_effective_plan_id(
            client_id,
            base_plan_id=base_plan_id,
            supabase_client=supabase,
        )
        if effective_plan_id != base_plan_id:
            override_plan_res = _run_timed(
                perf_ms,
                "override_plan_query",
                lambda: _with_retries(
                    lambda: (
                        supabase.table("plans")
                        .select(
                            "id, name, description, max_messages, max_documents, "
                            "is_unlimited, show_powered_by, supports_chat, supports_email, "
                            "supports_whatsapp, price_usd, duration, "
                            "plan_features(feature, is_active)"
                        )
                        .eq("id", effective_plan_id)
                        .maybe_single()
                        .execute()
                    ),
                    op_name="client_settings.override_plan",
                ),
            )
            if override_plan_res and override_plan_res.data:
                plan = override_plan_res.data

        # 🔹 Filtrar features activas
        raw_features = plan.get("plan_features", []) or []

        active_features = [
            f["feature"]
            for f in raw_features
            if f.get("is_active") is True
        ]

        plan["plan_features"] = active_features

        settings["plan"] = plan



        # Fallback de prompt
        if not settings.get("custom_prompt"):
            settings["custom_prompt"] = DEFAULT_PROMPT

        # 🎨 Fallback de fuente
        font_raw = settings.get("font_family", "")
        if not font_raw or font_raw.strip() == "":
            font_raw = "Inter, sans-serif"
        else:
            font_raw = font_raw.replace("'", "").replace('"', "").strip()
            font_name = font_raw.split(",")[0].strip()
            if font_name not in ALLOWED_FONTS:
                print(f"⚠️ Fuente desconocida ({font_name}), usando Inter por defecto.")
                font_raw = "Inter, sans-serif"

        settings["font_family"] = font_raw

        # Si plan no es premium/white_label, aplicar tema base
        plan_id = normalize_plan_id(plan["id"])
        if plan_id not in ["premium", "white_label"]:
            settings.update({
                "header_color": settings.get("header_color") or "#fff9f0",
                "header_text_color": settings.get("header_text_color") or "#1b2a41",
                "background_color": settings.get("background_color") or "#ffffff",
                "user_message_color": settings.get("user_message_color") or "#a3d9b1",
                "bot_message_color": settings.get("bot_message_color") or "#f7f7f7",
                "button_color": settings.get("button_color") or "#f5a623",
                "button_text_color": settings.get("button_text_color") or "#ffffff",
                "footer_text_color": settings.get("footer_text_color") or "#999999",
                "launcher_icon_url": None,
                "widget_height": settings.get("widget_height") or 420,
                "widget_border_radius": settings.get("widget_border_radius") or 13,
                "show_logo": settings.get("show_logo", True),
                "tooltip_bg_color": settings.get("tooltip_bg_color") or "#FFF8E1",
                "tooltip_text_color": settings.get("tooltip_text_color") or "#5C4B00",
                "consent_bg_color": settings.get("consent_bg_color") or "#FFF8E6",
                "consent_text_color": settings.get("consent_text_color") or "#7A4F00",
                "max_messages_per_session": settings.get("max_messages_per_session") or 20
            })

        # Listar planes disponibles
        plans_response = _run_timed(
            perf_ms,
            "available_plans_query",
            lambda: _with_retries(
                lambda: (
                    supabase.table("plans")
                    .select("""
                id, name, description, max_messages, max_documents,
                is_unlimited, supports_chat, supports_email, supports_whatsapp,
                show_powered_by, price_usd, duration,
                plan_features(feature, is_active)
                    """)
                    .order("price_usd")
                    .execute()
                ),
                op_name="client_settings.available_plans",
            ),
        )
        available_plans = plans_response.data or []
        for p in available_plans:
            raw_plan_features = p.get("plan_features", []) or []
            p["plan_features"] = [
                f["feature"]
                for f in raw_plan_features
                if f.get("is_active") is True
            ]
        settings["available_plans"] = available_plans

        total_ms = round((time.perf_counter() - request_started) * 1000, 1)
        perf_ms["total"] = total_ms
        logging.info("⏱️ client_settings timings | client_id=%s | %s", client_id, perf_ms)

        return JSONResponse(content=settings)

    except HTTPException:
        total_ms = round((time.perf_counter() - request_started) * 1000, 1)
        perf_ms["total"] = total_ms
        logging.info("⏱️ client_settings early-exit timings | client_id=%s | %s", client_id, perf_ms)
        raise
    except Exception as e:
        total_ms = round((time.perf_counter() - request_started) * 1000, 1)
        perf_ms["total"] = total_ms
        logging.error("⏱️ client_settings failed timings | client_id=%s | %s", client_id, perf_ms)
        print(f"❌ Error en GET /client_settings: {e}")
        if _is_transient_network_error(e):
            raise HTTPException(status_code=503, detail="Servicio temporalmente no disponible. Intenta nuevamente.")
        raise HTTPException(status_code=500, detail=f"Error al obtener configuración: {str(e)}")
