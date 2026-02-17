from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from api.modules.assistant_rag.supabase_client import supabase
from api.authz import authorize_client_request
import logging
from datetime import datetime
import time
import httpx

router = APIRouter()


_TRANSIENT_ERROR_MARKERS = (
    "server disconnected",
    "remoteprotocolerror",
    "readtimeout",
    "connection reset",
    "eof",
    "http2",
)


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


def _is_no_rows_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "406 not acceptable" in msg
        or "'code': '204'" in msg
        or '"code": "204"' in msg
        or "missing response" in msg
        or "0 rows" in msg
    )


def format_date(dt_str):
    """Convierte un string SQL o ISO en un formato legible (ej: Oct 14, 2025)"""
    if not dt_str:
        return None
    try:
        if "T" not in dt_str:
            dt_str = dt_str.replace(" ", "T")
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception as e:
        logging.warning(f"⚠️ No se pudo formatear fecha '{dt_str}': {e}")
        return dt_str


def count_bucket_documents(client_id: str) -> int:
    """Cuenta los archivos en el bucket evolvian-documents."""
    try:
        total_files = 0
        root_files = _with_retries(
            lambda: supabase.storage.from_("evolvian-documents").list(path=client_id),
            op_name="storage.list.root",
        )
        for f in root_files:
            if f["id"].endswith("/"):  # 📁 subcarpeta
                subfiles = _with_retries(
                    lambda: supabase.storage.from_("evolvian-documents").list(path=f["name"]),
                    op_name="storage.list.subfolder",
                )
                total_files += len(subfiles)
            else:
                total_files += 1
        return total_files
    except Exception as e:
        logging.error(f"❌ Error contando documentos en bucket: {e}")
        return 0


@router.get("/dashboard_summary")
def dashboard_summary(request: Request, client_id: str = Query(...)):
    request_started = time.perf_counter()
    perf_ms = {}
    try:
        _run_timed(perf_ms, "authorize_client_request", lambda: authorize_client_request(request, client_id))
        logging.info(f"📊 Obteniendo dashboard_summary para client_id={client_id}")

        # 1️⃣ Configuración del asistente y plan
        settings_res = _run_timed(
            perf_ms,
            "settings_query",
            lambda: _with_retries(
                lambda: (
                    supabase.table("client_settings")
                    .select(
                        "assistant_name, language, temperature, plan_id, show_powered_by, "
                        "subscription_start, subscription_end, cancellation_requested_at, scheduled_plan_id, "
                        "plans!client_settings_plan_id_fkey("
                        "id, name, max_messages, max_documents, is_unlimited, "
                        "show_powered_by, supports_chat, supports_email, supports_whatsapp, price_usd, "
                        "plan_features(feature, is_active)"
                        ")"
                    )
                    .eq("client_id", client_id)
                    .single()
                    .execute()
                ),
                op_name="dashboard.settings",
            ),
        )

        if not settings_res.data:
            raise HTTPException(status_code=404, detail="client_id no encontrado")

        config = settings_res.data
        plan = config.get("plans", {})

        # 2️⃣ Obtener información de suscripción
        sub_data = {
            "subscription_start": config.get("subscription_start"),
            "subscription_end": config.get("subscription_end"),
            "cancellation_requested_at": config.get("cancellation_requested_at"),
            "scheduled_plan_id": config.get("scheduled_plan_id"),
        }

        # 🧩 Nuevo bloque: estado de cancelación
        cancellation_status = None
        if sub_data.get("cancellation_requested_at"):
            plan_name = plan.get("name", "").capitalize() or config.get("plan_id", "Your plan").capitalize()
            cancel_date = format_date(sub_data.get("subscription_end"))
            next_plan = sub_data.get("scheduled_plan_id", "Free").capitalize()
            cancellation_status = {
                "is_pending": True,
                "message": f"⚠️ Your {plan_name} will be downgraded to {next_plan} on {cancel_date}.",
                "reactivate_label": f"🔄 Reactivate {plan_name}",
                "reactivate_available": True
            }


        # 3️⃣ Construir bloque del plan con datos combinados
        raw_features = plan.get("plan_features", []) or []

        active_features = [
            f["feature"]
            for f in raw_features
            if f.get("is_active") is True
        ]

        plan_info = {
            "id": plan.get("id"),
            "name": plan.get("name"),
            "max_messages": plan.get("max_messages"),
            "max_documents": plan.get("max_documents"),
            "is_unlimited": plan.get("is_unlimited"),
            "show_powered_by": plan.get("show_powered_by"),
            "supports_chat": plan.get("supports_chat"),
            "supports_email": plan.get("supports_email"),
            "supports_whatsapp": plan.get("supports_whatsapp"),
            "price_usd": plan.get("price_usd"),
            "plan_features": active_features,
        }


        # 4️⃣ Contar mensajes de usuario (solo role=user)
        msg_count_res = _run_timed(
            perf_ms,
            "history_count_query",
            lambda: _with_retries(
                lambda: (
                    supabase.table("history")
                    .select("id", count="exact")
                    .eq("client_id", client_id)
                    .eq("role", "user")
                    .execute()
                ),
                op_name="dashboard.message_count",
            ),
        )
        total_user_messages = getattr(msg_count_res, "count", 0) or 0
        logging.info(f"💬 Mensajes de usuario encontrados: {total_user_messages}")

        # 5️⃣ Leer uso actual (para fallback/caché)
        try:
            usage_row = _run_timed(
                perf_ms,
                "usage_read_query",
                lambda: _with_retries(
                    lambda: (
                        supabase.table("client_usage")
                        .select("messages_used, documents_uploaded, last_used_at")
                        .eq("client_id", client_id)
                        .limit(1)
                        .execute()
                    ),
                    op_name="dashboard.usage_read",
                ),
            )
            usage_data = (usage_row.data or [{}])[0] if isinstance(usage_row.data, list) else (usage_row.data or {})
        except Exception as usage_read_exc:
            if _is_no_rows_error(usage_read_exc):
                logging.info("ℹ️ client_usage sin registro para client_id=%s (se inicializa en memoria)", client_id)
                usage_data = {}
            else:
                raise

        usage = {
            "messages_used": total_user_messages,
            "documents_uploaded": usage_data.get("documents_uploaded") or 0,
            "last_used_at": datetime.utcnow().isoformat(),
        }

        # Escritura de usage en modo best-effort para no tirar el endpoint
        try:
            _run_timed(
                perf_ms,
                "usage_upsert_write",
                lambda: _with_retries(
                    lambda: (
                        supabase.table("client_usage")
                        .upsert(
                            {
                                "client_id": client_id,
                                "messages_used": total_user_messages,
                                "documents_uploaded": usage["documents_uploaded"],
                                "last_used_at": usage["last_used_at"],
                            },
                            on_conflict="client_id",
                        )
                        .execute()
                    ),
                    op_name="dashboard.usage_upsert",
                ),
            )
        except Exception as usage_exc:
            logging.warning("⚠️ No se pudo sincronizar usage (non-blocking): %s", usage_exc)

        # 6️⃣ Contar documentos en bucket solo bajo demanda o sin caché
        refresh_docs = request.query_params.get("refresh_documents") == "1"
        if refresh_docs or usage["documents_uploaded"] == 0:
            bucket_count = _run_timed(
                perf_ms,
                "documents_count_storage",
                lambda: count_bucket_documents(client_id),
            )
            usage["documents_uploaded"] = bucket_count
            try:
                _run_timed(
                    perf_ms,
                    "documents_upsert_write",
                    lambda: _with_retries(
                        lambda: (
                            supabase.table("client_usage")
                            .upsert(
                                {
                                    "client_id": client_id,
                                    "documents_uploaded": bucket_count,
                                    "messages_used": total_user_messages,
                                    "last_used_at": usage["last_used_at"],
                                },
                                on_conflict="client_id",
                            )
                            .execute()
                        ),
                        op_name="dashboard.usage_docs_upsert",
                    ),
                )
            except Exception as docs_exc:
                logging.warning("⚠️ No se pudo guardar documents_uploaded (non-blocking): %s", docs_exc)

        # 7️⃣ Canales activos
        channels_res = _run_timed(
            perf_ms,
            "channels_query",
            lambda: _with_retries(
                lambda: supabase.table("channels").select("type").eq("client_id", client_id).execute(),
                op_name="dashboard.channels",
            ),
        )
        active_channels = [c["type"] for c in channels_res.data or []]
        all_channels = ["chat", "whatsapp", "email"]
        channels = {c: c in active_channels for c in all_channels}

        # 8️⃣ Historial de usuario (últimos 3)
        history_res = _run_timed(
            perf_ms,
            "history_preview_query",
            lambda: _with_retries(
                lambda: (
                    supabase.table("history")
                    .select("content, created_at, channel, role")
                    .eq("client_id", client_id)
                    .eq("role", "user")
                    .not_.is_("content", None)
                    .neq("content", "")
                    .order("created_at", desc=True)
                    .limit(3)
                    .execute()
                ),
                op_name="dashboard.history_preview",
            ),
        )

        history_preview = []
        for h in history_res.data or []:
            content = h.get("content")
            if isinstance(content, dict):
                content = content.get("text") or str(content)
            if not content or not str(content).strip():
                continue

            history_preview.append({
                "timestamp": h.get("created_at"),
                "channel": h.get("channel", "chat"),
                "question": str(content).strip()[:120],
            })

        # 9️⃣ Sugerencia de upgrade
        upgrade_suggestion = None
        if not plan_info["is_unlimited"] and plan_info["max_messages"]:
            percent = (usage["messages_used"] / plan_info["max_messages"]) * 100
            if percent >= 80:
                if plan_info["id"] == "free":
                    upgrade_suggestion = {"action": "upgrade", "to": "starter"}
                elif plan_info["id"] == "starter":
                    upgrade_suggestion = {"action": "upgrade", "to": "premium"}
                elif plan_info["id"] == "premium":
                    upgrade_suggestion = {"action": "contact_support", "email": "support@evolvianai.com"}

        # ✅ Respuesta final (todo igual, solo agrega el nuevo campo)
        total_ms = round((time.perf_counter() - request_started) * 1000, 1)
        perf_ms["total"] = total_ms
        logging.info("⏱️ dashboard_summary timings | client_id=%s | %s", client_id, perf_ms)

        return JSONResponse(
            content={
                "plan": plan_info,
                "usage": usage,
                "channels": channels,
                "assistant_config": {
                    "assistant_name": config.get("assistant_name", "Evolvian"),
                    "language": config.get("language", "es"),
                    "temperature": config.get("temperature", 0.7),
                    "show_powered_by": config.get("show_powered_by", True),
                },
                "history_preview": history_preview,
                "upgrade_suggestion": upgrade_suggestion,
                "subscription_start": format_date(plan_info.get("subscription_start") or sub_data.get("subscription_start")),
                "subscription_end": format_date(plan_info.get("subscription_end") or sub_data.get("subscription_end")),
                "cancellation_status": cancellation_status,  # 🧩 nuevo campo aquí
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        total_ms = round((time.perf_counter() - request_started) * 1000, 1)
        perf_ms["total"] = total_ms
        logging.error("⏱️ dashboard_summary failed timings | client_id=%s | %s", client_id, perf_ms)
        logging.exception("❌ Error en /dashboard_summary")
        raise HTTPException(status_code=500, detail="Error al obtener el resumen del cliente.")
