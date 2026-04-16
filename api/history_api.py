from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import JSONResponse

from api.authz import authorize_client_request
from api.modules.assistant_rag.llm import openai_chat
from api.modules.assistant_rag.supabase_client import supabase
from api.utils.feature_access import require_client_feature

router = APIRouter()
logger = logging.getLogger(__name__)


SYSTEM_SOURCE_TYPES = {
    "analytics_event",
    "compliance_outbound_policy",
}

QUESTION_WORDS = (
    "what",
    "when",
    "where",
    "who",
    "why",
    "how",
    "can",
    "could",
    "do",
    "does",
    "is",
    "are",
    "que",
    "qué",
    "como",
    "cómo",
    "cuando",
    "cuándo",
    "donde",
    "dónde",
    "cual",
    "cuál",
    "cuanto",
    "cuánto",
    "puedo",
    "pueden",
    "tienen",
    "hay",
)

TOPIC_KEYWORDS = {
    "appointments": {
        "label": {"es": "Citas y agenda", "en": "Appointments and scheduling"},
        "goal": {
            "es": "Reservar, mover o confirmar una cita",
            "en": "Book, reschedule, or confirm an appointment",
        },
        "keywords": {
            "appointment",
            "appointments",
            "schedule",
            "scheduling",
            "book",
            "booking",
            "calendar",
            "availability",
            "available",
            "slot",
            "slots",
            "agendar",
            "agenda",
            "cita",
            "citas",
            "reservar",
            "reservacion",
            "reservación",
            "disponibilidad",
            "horario",
        },
    },
    "pricing": {
        "label": {"es": "Precios y cotizaciones", "en": "Pricing and quotes"},
        "goal": {
            "es": "Entender precios, promociones o cotizaciones",
            "en": "Understand pricing, promotions, or quotes",
        },
        "keywords": {
            "price",
            "prices",
            "pricing",
            "quote",
            "quotes",
            "budget",
            "cost",
            "costs",
            "fee",
            "fees",
            "precio",
            "precios",
            "costo",
            "costos",
            "cotizacion",
            "cotización",
            "promocion",
            "promoción",
            "descuento",
        },
    },
    "business_hours": {
        "label": {"es": "Horarios y disponibilidad", "en": "Business hours and availability"},
        "goal": {
            "es": "Saber cuándo pueden atender o responder",
            "en": "Know when the business can respond or receive visitors",
        },
        "keywords": {
            "hours",
            "hour",
            "open",
            "opening",
            "closing",
            "closed",
            "today",
            "tomorrow",
            "horario",
            "horarios",
            "abren",
            "cierran",
            "abierto",
            "cerrado",
            "atienden",
            "manana",
            "mañana",
            "hoy",
        },
    },
    "location": {
        "label": {"es": "Ubicación y contacto", "en": "Location and contact details"},
        "goal": {
            "es": "Encontrar la sucursal correcta o un canal de contacto",
            "en": "Find the right branch or contact channel",
        },
        "keywords": {
            "address",
            "location",
            "located",
            "map",
            "maps",
            "directions",
            "phone",
            "email",
            "direccion",
            "dirección",
            "ubicacion",
            "ubicación",
            "telefono",
            "teléfono",
            "correo",
            "sucursal",
        },
    },
    "services": {
        "label": {"es": "Servicios y alcance", "en": "Services and scope"},
        "goal": {
            "es": "Confirmar si ofrecen un servicio o solución específica",
            "en": "Confirm whether a specific service or solution is offered",
        },
        "keywords": {
            "service",
            "services",
            "offer",
            "offers",
            "include",
            "includes",
            "support",
            "producto",
            "productos",
            "servicio",
            "servicios",
            "ofrecen",
            "incluye",
            "incluyen",
            "ayuda",
            "soporte",
        },
    },
}

STOPWORDS = {
    "about",
    "also",
    "and",
    "are",
    "can",
    "como",
    "con",
    "cual",
    "cuál",
    "cuando",
    "cuándo",
    "donde",
    "dónde",
    "does",
    "from",
    "have",
    "hola",
    "how",
    "los",
    "las",
    "para",
    "por",
    "price",
    "que",
    "qué",
    "quiero",
    "this",
    "tienen",
    "una",
    "what",
    "where",
    "with",
    "your",
}


def _is_system_history_event(row: dict[str, Any]) -> bool:
    source_type = str(row.get("source_type") or "").strip().lower()
    if source_type in SYSTEM_SOURCE_TYPES:
        return True

    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        compliance_event = str(metadata.get("compliance_event") or "").strip().lower()
        if compliance_event == "outbound_policy":
            return True

    session_id = str(row.get("session_id") or "")
    content = str(row.get("content") or "").strip().lower()
    if session_id.startswith("proof_") and content.startswith("outbound policy "):
        return True

    return False


def _normalize_lang(lang: str | None) -> str:
    return "en" if str(lang or "").strip().lower().startswith("en") else "es"


def _parse_created_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    text = str(value or "").strip()
    if not text:
        return datetime.fromtimestamp(0, tz=timezone.utc)

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _load_history_rows(
    client_id: str,
    session_id: str | None = None,
    limit: int = 50,
    include_system_events: bool = False,
) -> list[dict[str, Any]]:
    raw_limit = limit if include_system_events else min(limit * 4, 800)
    query = (
        supabase.table("history")
        .select(
            """
                role,
                content,
                created_at,
                session_id,
                channel,
                source_type,
                provider,
                status,
                source_id,
                metadata
            """
        )
        .eq("client_id", client_id)
    )

    if session_id:
        query = query.eq("session_id", session_id)

    response = query.order("created_at", desc=True).limit(raw_limit).execute()
    raw_data = response.data or []
    logger.info("📦 Registros encontrados: %s", len(raw_data))

    results: list[dict[str, Any]] = []
    for row in raw_data:
        if not isinstance(row, dict):
            continue
        if not row.get("content"):
            continue
        if not include_system_events and _is_system_history_event(row):
            continue

        results.append(
            {
                "role": row.get("role"),
                "content": row.get("content"),
                "created_at": row.get("created_at"),
                "session_id": row.get("session_id"),
                "channel": row.get("channel", "chat"),
                "source_type": row.get("source_type", "chat"),
                "provider": row.get("provider", "internal"),
                "status": row.get("status", "sent"),
                "source_id": row.get("source_id"),
                "metadata": row.get("metadata"),
            }
        )
        if len(results) >= limit:
            break

    return results


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _short_session_id(session_id: str | None) -> str:
    normalized = str(session_id or "default").strip() or "default"
    return normalized[:8]


def _extract_json_object(value: str) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not text or text.lower().startswith("error:"):
        return None

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None

    try:
        parsed = json.loads(text[first:last + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _top_channel_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row.get("channel") or "chat").strip().lower() or "chat" for row in rows)
    return [
        {"channel": channel, "count": count}
        for channel, count in counts.most_common(4)
    ]


def _detect_repeated_questions(user_messages: list[str]) -> list[dict[str, Any]]:
    question_counts: Counter[str] = Counter()
    question_display: dict[str, str] = {}

    for message in user_messages:
        normalized = _normalize_text(message)
        if not normalized:
            continue

        lowered = normalized.lower()
        is_question = "?" in normalized or lowered.split(" ", 1)[0] in QUESTION_WORDS
        if not is_question:
            continue

        compact = re.sub(r"[?!]+$", "", lowered).strip()
        if len(compact) < 6:
            continue

        question_counts[compact] += 1
        question_display.setdefault(compact, normalized[:180])

    return [
        {
            "question": question_display[key],
            "mentions": count,
        }
        for key, count in question_counts.most_common(5)
    ]


def _detect_topics(user_messages: list[str], lang: str) -> list[dict[str, Any]]:
    topic_counts: Counter[str] = Counter()
    keyword_counts: Counter[str] = Counter()

    for message in user_messages:
        normalized = _normalize_text(message).lower()
        if not normalized:
            continue

        matched_topics = set()
        for topic_key, topic_config in TOPIC_KEYWORDS.items():
            if any(keyword in normalized for keyword in topic_config["keywords"]):
                matched_topics.add(topic_key)

        for topic_key in matched_topics:
            topic_counts[topic_key] += 1

        for token in re.findall(r"[A-Za-zÀ-ÿ0-9]{4,}", normalized):
            if token in STOPWORDS or token.isdigit():
                continue
            keyword_counts[token] += 1

    topics = [
        {
            "topic": TOPIC_KEYWORDS[topic_key]["label"][lang],
            "mentions": count,
            "note": TOPIC_KEYWORDS[topic_key]["goal"][lang],
        }
        for topic_key, count in topic_counts.most_common(5)
    ]

    if topics:
        return topics

    return [
        {
            "topic": keyword.title(),
            "mentions": count,
            "note": "",
        }
        for keyword, count in keyword_counts.most_common(5)
    ]


def _build_unresolved_sessions(
    sessions: dict[str, list[dict[str, Any]]],
    lang: str,
) -> list[dict[str, Any]]:
    items = []
    for session_id, messages in sessions.items():
        ordered = sorted(messages, key=lambda row: _parse_created_at(row.get("created_at")))
        last_message = ordered[-1] if ordered else {}
        last_role = str(last_message.get("role") or "").strip().lower()
        if last_role != "user":
            continue

        reason = (
            "La conversación parece terminar con una pregunta del cliente."
            if lang == "es"
            else "The conversation appears to end with a customer question."
        )
        items.append(
            {
                "session_id": session_id,
                "display_id": _short_session_id(session_id),
                "last_message_at": last_message.get("created_at"),
                "reason": reason,
            }
        )

    items.sort(key=lambda row: _parse_created_at(row.get("last_message_at")), reverse=True)
    return items[:4]


def _build_fallback_recommendations(
    faq: list[dict[str, Any]],
    top_topics: list[dict[str, Any]],
    unresolved_sessions: list[dict[str, Any]],
    lang: str,
) -> list[str]:
    recommendations: list[str] = []

    if faq:
        recommendations.append(
            "Conviene publicar una FAQ corta con las preguntas que más se repiten."
            if lang == "es"
            else "A short FAQ covering the most repeated questions would reduce repetition."
        )
    if top_topics:
        recommendations.append(
            "Puedes crear respuestas rápidas o snippets para los temas con más volumen."
            if lang == "es"
            else "Create quick replies or snippets for the highest-volume topics."
        )
    if unresolved_sessions:
        recommendations.append(
            "Revisa las conversaciones cuyo último turno quedó del lado del cliente."
            if lang == "es"
            else "Review conversations where the latest turn still belongs to the customer."
        )

    if not recommendations:
        recommendations.append(
            "Todavía no hay suficiente historial para detectar patrones fuertes."
            if lang == "es"
            else "There is not enough history yet to identify strong patterns."
        )

    return recommendations[:4]


def _build_fallback_insights(rows: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        session_id = str(row.get("session_id") or "default")
        sessions[session_id].append(row)

    user_messages = [
        _normalize_text(row.get("content"))
        for row in rows
        if str(row.get("role") or "").strip().lower() == "user"
    ]
    user_messages = [message for message in user_messages if message]

    faq = _detect_repeated_questions(user_messages)
    top_topics = _detect_topics(user_messages, lang)
    unresolved_sessions = _build_unresolved_sessions(sessions, lang)

    customer_goals = []
    for topic in top_topics[:4]:
        note = str(topic.get("note") or "").strip()
        if note and note not in customer_goals:
            customer_goals.append(note)

    friction_points = []
    if faq and faq[0]["mentions"] > 1:
        friction_points.append(
            "Hay preguntas muy repetidas, lo que sugiere falta de información visible antes del chat."
            if lang == "es"
            else "Repeated questions suggest some information is still hard to find before the chat starts."
        )
    if unresolved_sessions:
        friction_points.append(
            "Varias conversaciones terminan con el cliente esperando la siguiente respuesta."
            if lang == "es"
            else "Several conversations end while the customer is still waiting for the next answer."
        )
    if not friction_points and rows:
        friction_points.append(
            "No se observa un bloqueo dominante, pero conviene seguir monitoreando volumen y cierres."
            if lang == "es"
            else "No single dominant blocker stands out yet, but volume and closures should still be monitored."
        )

    conversation_count = len(sessions)
    avg_messages = round(len(rows) / conversation_count, 1) if conversation_count else 0.0
    summary = (
        f"Se analizaron {conversation_count} conversaciones y {len(rows)} mensajes. "
        f"Los temas dominantes giran alrededor de {top_topics[0]['topic'].lower()}."
        if lang == "es" and top_topics
        else (
            f"Analyzed {conversation_count} conversations and {len(rows)} messages. "
            f"The strongest pattern is around {top_topics[0]['topic'].lower()}."
            if top_topics
            else (
                f"Se analizaron {conversation_count} conversaciones recientes."
                if lang == "es"
                else f"Analyzed {conversation_count} recent conversations."
            )
        )
    )

    return {
        "provider": "heuristic",
        "summary": summary,
        "stats": {
            "conversation_count": conversation_count,
            "message_count": len(rows),
            "avg_messages_per_conversation": avg_messages,
            "active_channels": _top_channel_counts(rows),
        },
        "faq": faq,
        "top_topics": top_topics,
        "customer_goals": customer_goals[:4],
        "friction_points": friction_points[:4],
        "recommendations": _build_fallback_recommendations(
            faq,
            top_topics,
            unresolved_sessions,
            lang,
        ),
        "unresolved_sessions": unresolved_sessions,
    }


def _build_history_sample(rows: list[dict[str, Any]]) -> str:
    sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        sessions[str(row.get("session_id") or "default")].append(row)

    sorted_sessions = sorted(
        sessions.items(),
        key=lambda item: max(_parse_created_at(message.get("created_at")) for message in item[1]),
        reverse=True,
    )

    sections: list[str] = []
    for session_id, messages in sorted_sessions[:8]:
        ordered = sorted(messages, key=lambda row: _parse_created_at(row.get("created_at")))
        channel = str((ordered[0] if ordered else {}).get("channel") or "chat")
        sections.append(
            f"Session {session_id} | channel={channel} | messages={len(ordered)}"
        )
        for message in ordered[-8:]:
            role = str(message.get("role") or "assistant").strip().lower() or "assistant"
            content = _normalize_text(message.get("content"))[:240]
            if content:
                sections.append(f"{role}: {content}")
        sections.append("")

    return "\n".join(sections)[:7000]


def _normalize_ai_items(items: Any, key_name: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in list(items or [])[:5]:
        if isinstance(item, dict):
            label = _normalize_text(item.get(key_name))
            mentions = item.get("mentions")
            note = _normalize_text(item.get("note"))
        else:
            label = _normalize_text(item)
            mentions = 1
            note = ""

        if not label:
            continue

        try:
            parsed_mentions = max(int(mentions), 1)
        except Exception:
            parsed_mentions = 1

        entry = {key_name: label, "mentions": parsed_mentions}
        if note:
            entry["note"] = note
        normalized.append(entry)
    return normalized


def _normalize_ai_text_list(items: Any) -> list[str]:
    normalized: list[str] = []
    for item in list(items or [])[:5]:
        value = _normalize_text(item)
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _generate_ai_insights(
    rows: list[dict[str, Any]],
    fallback: dict[str, Any],
    lang: str,
) -> dict[str, Any] | None:
    if not rows:
        return None

    stats = fallback.get("stats") or {}
    language_name = "English" if lang == "en" else "Spanish"
    prompt = (
        "Analyze these customer conversations for an operations dashboard.\n"
        f"Reply in {language_name}.\n"
        "Return strict JSON only with this schema:\n"
        "{"
        '"summary":"string",'
        '"faq":[{"question":"string","mentions":2,"note":"string"}],'
        '"top_topics":[{"topic":"string","mentions":2,"note":"string"}],'
        '"customer_goals":["string"],'
        '"friction_points":["string"],'
        '"recommendations":["string"]'
        "}\n"
        "Use at most 5 items per list. Keep the summary under 280 characters. "
        "Do not use markdown or code fences.\n\n"
        f"Known stats: conversations={stats.get('conversation_count', 0)}, "
        f"messages={stats.get('message_count', 0)}, "
        f"avg_messages_per_conversation={stats.get('avg_messages_per_conversation', 0)}.\n"
        f"Existing heuristic FAQ candidates: {json.dumps(fallback.get('faq') or [], ensure_ascii=False)}\n"
        f"Existing heuristic topics: {json.dumps(fallback.get('top_topics') or [], ensure_ascii=False)}\n"
        f"Potential unresolved sessions: {json.dumps(fallback.get('unresolved_sessions') or [], ensure_ascii=False)}\n\n"
        "Conversation sample:\n"
        f"{_build_history_sample(rows)}"
    )

    try:
        raw = openai_chat(
            [
                {
                    "role": "system",
                    "content": "You are a conversation analyst for business customer support and appointment flows.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            model="gpt-4o-mini",
            timeout=18,
        )
    except Exception as exc:
        logger.warning("History insights AI fallback triggered: %s", exc)
        return None

    parsed = _extract_json_object(raw)
    if not parsed:
        return None

    summary = _normalize_text(parsed.get("summary"))
    faq = _normalize_ai_items(parsed.get("faq"), "question")
    top_topics = _normalize_ai_items(parsed.get("top_topics"), "topic")
    customer_goals = _normalize_ai_text_list(parsed.get("customer_goals"))
    friction_points = _normalize_ai_text_list(parsed.get("friction_points"))
    recommendations = _normalize_ai_text_list(parsed.get("recommendations"))

    merged = dict(fallback)
    merged["provider"] = "openai"
    if summary:
        merged["summary"] = summary
    if faq:
        merged["faq"] = faq
    if top_topics:
        merged["top_topics"] = top_topics
    if customer_goals:
        merged["customer_goals"] = customer_goals
    if friction_points:
        merged["friction_points"] = friction_points
    if recommendations:
        merged["recommendations"] = recommendations
    return merged


@router.get("/history")
def get_history(
    request: Request,
    client_id: str = Query(...),
    session_id: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    include_system_events: bool = Query(False),
):
    """
    Devuelve el historial de un cliente.
    - Compatible con versión actual
    - Compatible con nuevas columnas (source_type, provider, status, etc.)
    - No rompe frontend existente
    """

    try:
        authorize_client_request(request, client_id)
        logger.info(
            "📥 /history | client_id=%s | session_id=%s | include_system_events=%s",
            client_id,
            session_id,
            include_system_events,
        )
        results = _load_history_rows(
            client_id=client_id,
            session_id=session_id,
            limit=limit,
            include_system_events=include_system_events,
        )

        if results:
            logger.info(
                f"🧩 Último mensaje: {results[0]['role']} - "
                f"{results[0]['content'][:60]}"
            )
        else:
            logger.info("ℹ️ No hay mensajes válidos para mostrar.")

        return JSONResponse(
            content={
                "client_id": client_id,
                "session_id": session_id,
                "count": len(results),
                "history": results,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("❌ Error en /history")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )


@router.get("/history/insights")
def get_history_insights(
    request: Request,
    client_id: str = Query(...),
    limit: int = Query(180, ge=20, le=400),
    include_system_events: bool = Query(False),
    lang: str = Query("es"),
):
    try:
        authorize_client_request(request, client_id)
        require_client_feature(
            client_id,
            "conversation_insights",
            required_plan_label="premium",
        )
        normalized_lang = _normalize_lang(lang)
        rows = _load_history_rows(
            client_id=client_id,
            session_id=None,
            limit=limit,
            include_system_events=include_system_events,
        )
        fallback = _build_fallback_insights(rows, normalized_lang)
        insights = _generate_ai_insights(rows, fallback, normalized_lang) or fallback
        insights["client_id"] = client_id
        insights["generated_at"] = datetime.now(timezone.utc).isoformat()
        insights["language"] = normalized_lang
        return insights
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("❌ Error en /history/insights")
        raise HTTPException(status_code=500, detail=f"History insights error: {exc}")
