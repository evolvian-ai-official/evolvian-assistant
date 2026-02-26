#!/usr/bin/env python3
"""
Staging smoke checks for direct scheduling intent across channels.

Goals:
- Verify scheduling prompts route to scheduling flow
- Verify non-scheduling prompts do NOT route to scheduling flow
- Check basic language consistency (es/en) in responses

This script can run:
- Widget chat (`/api/chat` by default)
- Email chat (`/chat_email` by default)
- Twilio webhook (`/api/twilio-webhook`) if configured
- Meta webhook (`/api/webhooks/meta`) if configured

Optional strong validation:
- Query `/history` with a bearer token to validate `source_type`, `channel`, `provider`
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from typing import Any
from urllib.parse import urljoin

import requests

try:
    from twilio.request_validator import RequestValidator
except Exception:  # pragma: no cover - optional in local environments
    RequestValidator = None


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _path_candidates(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _pick_url(base_url: str, candidates: list[str]) -> str:
    if not candidates:
        raise ValueError("No route candidates provided")
    return urljoin(base_url.rstrip("/") + "/", candidates[0].lstrip("/"))


def _detect_lang(text: str) -> str:
    t = (text or "").lower()
    spanish_signals = {
        "¿", "¡", "á", "é", "í", "ó", "ú", "ñ",
        "hola", "gracias", "quiero", "necesito", "agendar", "reservar",
        "cita", "horario", "horarios", "precio", "precios", "planes",
        "correo", "disponible", "disponibilidad",
    }
    if any(s in t for s in spanish_signals):
        return "es"
    return "en"


SCHEDULING_HINTS = (
    "agend", "cita", "horario", "dispon", "reserv",
    "schedul", "appointment", "slot", "book",
)

NON_SCHEDULING_HINTS = (
    "plan", "precio", "pricing", "service", "servicio",
    "widget", "support", "soporte", "integrat", "integración",
)


def _looks_like_schedule_response(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in SCHEDULING_HINTS)


def _looks_like_non_schedule_response(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in NON_SCHEDULING_HINTS) and not any(k in t for k in ("confirmada", "appointment confirmed"))


@dataclasses.dataclass
class Case:
    id: str
    channel: str
    kind: str  # schedule | non_schedule
    expected_lang: str
    message: str


def _build_cases(prefix: str) -> list[Case]:
    return [
        Case(f"{prefix}_es_schedule", prefix, "schedule", "es", "Quiero agendar una cita para mañana"),
        Case(f"{prefix}_en_schedule", prefix, "schedule", "en", "I want to schedule an appointment for tomorrow"),
        Case(f"{prefix}_es_non_schedule", prefix, "non_schedule", "es", "Qué planes tienen y qué incluye el servicio?"),
        Case(f"{prefix}_en_non_schedule", prefix, "non_schedule", "en", "What plans do you offer and what is included?"),
    ]


def _meta_payload(message: str, user_phone: str, business_phone: str) -> bytes:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": business_phone},
                            "messages": [
                                {
                                    "from": user_phone,
                                    "type": "text",
                                    "text": {"body": message},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    return json.dumps(payload).encode("utf-8")


def _meta_signature(raw_body: bytes, app_secret: str) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _twilio_signature(url: str, body: dict[str, str], auth_token: str) -> str | None:
    if not auth_token:
        return None
    if RequestValidator is None:
        return None
    validator = RequestValidator(auth_token)
    return validator.compute_signature(url, body)


def _extract_text_from_response(channel: str, response: requests.Response) -> str:
    if channel == "twilio_whatsapp":
        return response.text
    if channel == "meta_whatsapp":
        return response.text
    try:
        data = response.json()
    except Exception:
        return response.text
    if isinstance(data, dict):
        return str(data.get("answer") or data)
    return str(data)


def _history_fetch(base_url: str, client_id: str, session_id: str, bearer_token: str, history_candidates: list[str]) -> dict[str, Any] | None:
    headers = {"Authorization": f"Bearer {bearer_token}"}
    for path in history_candidates:
        url = _pick_url(base_url, [path])
        try:
            res = requests.get(
                url,
                params={"client_id": client_id, "session_id": session_id, "limit": 10},
                headers=headers,
                timeout=15,
            )
        except requests.RequestException:
            continue
        if res.status_code == 200:
            try:
                return res.json()
            except Exception:
                return None
    return None


def _history_validate(history_payload: dict[str, Any], case: Case, expected_provider: str, expected_channel: str) -> tuple[bool, str]:
    rows = list((history_payload or {}).get("history") or [])
    if not rows:
        return False, "history empty"

    assistant = next((r for r in rows if r.get("role") == "assistant"), None)
    if not assistant:
        return False, "assistant row not found"

    source_type = str(assistant.get("source_type") or "")
    provider = str(assistant.get("provider") or "")
    channel = str(assistant.get("channel") or "")
    content = str(assistant.get("content") or "")

    if provider != expected_provider:
        return False, f"provider mismatch ({provider} != {expected_provider})"
    if channel != expected_channel:
        return False, f"channel mismatch ({channel} != {expected_channel})"

    if case.kind == "schedule" and source_type != "appointment":
        return False, f"expected source_type=appointment, got {source_type}"
    if case.kind == "non_schedule" and source_type == "appointment":
        return False, "unexpected appointment source_type"

    detected = _detect_lang(content)
    if detected != case.expected_lang:
        return False, f"history language mismatch ({detected} != {case.expected_lang})"

    return True, "ok"


def _basic_validate(case: Case, text: str) -> tuple[bool, str]:
    detected = _detect_lang(text)
    if detected != case.expected_lang:
        return False, f"language mismatch ({detected} != {case.expected_lang})"

    if case.kind == "schedule":
        if not _looks_like_schedule_response(text):
            return False, "response does not look like scheduling"
    else:
        if not _looks_like_non_schedule_response(text):
            return False, "response does not look like non-scheduling"

    return True, "ok"


def _run_widget_case(base_url: str, case: Case, public_client_id: str, widget_path: str) -> tuple[bool, str]:
    session_id = f"qa-widget-{case.id}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    url = _pick_url(base_url, [widget_path])
    payload = {
        "public_client_id": public_client_id,
        "session_id": session_id,
        "message": case.message,
        "channel": "chat",
    }
    res = requests.post(url, json=payload, timeout=20)
    if res.status_code != 200:
        return False, f"http {res.status_code}: {res.text[:200]}"
    try:
        body = res.json()
    except Exception:
        return False, f"invalid json: {res.text[:200]}"
    answer = str(body.get("answer") or "")
    if not answer:
        return False, "empty answer"
    ok, reason = _basic_validate(case, answer)
    if not ok:
        return False, f"{reason} | answer={answer[:200]}"
    return True, session_id


def _run_email_case(base_url: str, case: Case, from_email: str, email_path: str, internal_token: str) -> tuple[bool, str]:
    if not internal_token:
        return False, "missing EVOLVIAN_INTERNAL_TASK_TOKEN"
    url = _pick_url(base_url, [email_path])
    headers = {"x-evolvian-internal-token": internal_token}
    payload = {
        "from_email": from_email,
        "subject": "QA direct scheduling",
        "message": case.message,
    }
    res = requests.post(url, json=payload, headers=headers, timeout=20)
    if res.status_code != 200:
        return False, f"http {res.status_code}: {res.text[:200]}"
    try:
        body = res.json()
    except Exception:
        return False, f"invalid json: {res.text[:200]}"
    answer = str(body.get("answer") or "")
    session_id = str(body.get("session_id") or "")
    if not answer or not session_id:
        return False, f"missing answer/session_id: {body}"
    ok, reason = _basic_validate(case, answer)
    if not ok:
        return False, f"{reason} | answer={answer[:200]}"
    return True, session_id


def _run_twilio_case(base_url: str, case: Case, twilio_path: str, test_user_phone: str, auth_token: str | None) -> tuple[bool, str]:
    url = _pick_url(base_url, [twilio_path])
    from_number = f"whatsapp:{test_user_phone}"
    form = {"Body": case.message, "From": from_number}
    headers: dict[str, str] = {}
    sig = _twilio_signature(url, form, auth_token or "")
    if sig:
        headers["X-Twilio-Signature"] = sig
    res = requests.post(url, data=form, headers=headers, timeout=20)
    if res.status_code != 200:
        return False, f"http {res.status_code}: {res.text[:200]}"
    text = _extract_text_from_response("twilio_whatsapp", res)
    ok, reason = _basic_validate(case, text)
    if not ok:
        return False, f"{reason} | body={text[:200]}"
    session_id = f"whatsapp-{test_user_phone.replace('whatsapp:', '').strip()}"
    return True, session_id


def _run_meta_case(
    base_url: str,
    case: Case,
    meta_path: str,
    user_phone_digits: str,
    business_phone_digits: str,
    app_secret: str | None,
) -> tuple[bool, str]:
    url = _pick_url(base_url, [meta_path])
    raw = _meta_payload(case.message, user_phone_digits, business_phone_digits)
    headers = {"Content-Type": "application/json"}
    if app_secret:
        headers["X-Hub-Signature-256"] = _meta_signature(raw, app_secret)
    res = requests.post(url, data=raw, headers=headers, timeout=20)
    if res.status_code != 200:
        return False, f"http {res.status_code}: {res.text[:200]}"
    session_id = f"whatsapp-{user_phone_digits}"
    # Response body is {"status":"ok"}; actual assistant text is sent outbound to WhatsApp.
    return True, session_id


def main() -> int:
    base_url = _env("STAGING_BASE_URL")
    if not base_url:
        print("ERROR: missing STAGING_BASE_URL")
        return 2

    widget_path = _env("WIDGET_CHAT_PATH", "/api/chat")
    email_path = _env("EMAIL_CHAT_PATH", "/chat_email")
    twilio_path = _env("TWILIO_WEBHOOK_PATH", "/api/twilio-webhook")
    meta_path = _env("META_WEBHOOK_PATH", "/api/webhooks/meta")
    history_candidates = _path_candidates(_env("HISTORY_PATH_CANDIDATES", "/history,/api/history") or "")

    public_client_id = _env("WIDGET_PUBLIC_CLIENT_ID")
    email_from = _env("EMAIL_CHANNEL_ADDRESS")
    internal_token = _env("EVOLVIAN_INTERNAL_TASK_TOKEN")

    run_widget = _env_bool("RUN_WIDGET", True)
    run_email = _env_bool("RUN_EMAIL", True)
    run_twilio = _env_bool("RUN_TWILIO", False)
    run_meta = _env_bool("RUN_META", False)

    twilio_test_user_phone = _env("TWILIO_TEST_USER_PHONE", "+15557654321")
    twilio_auth_token = _env("TWILIO_AUTH_TOKEN")
    meta_user_phone_digits = _env("META_TEST_USER_PHONE_DIGITS", "15557654321")
    meta_business_phone_digits = _env("META_BUSINESS_DISPLAY_PHONE_DIGITS", "15551234567")
    meta_app_secret = _env("META_APP_SECRET")

    history_bearer = _env("HISTORY_BEARER_TOKEN")
    history_client_id = _env("HISTORY_CLIENT_ID")
    validate_history = bool(history_bearer and history_client_id)

    enabled_cases: list[Case] = []
    if run_widget:
        enabled_cases += _build_cases("widget_chat")
    if run_email:
        enabled_cases += _build_cases("email_chat")
    if run_twilio:
        enabled_cases += _build_cases("twilio_whatsapp")
    if run_meta:
        enabled_cases += _build_cases("meta_whatsapp")

    if not enabled_cases:
        print("No channels enabled. Set RUN_WIDGET/RUN_EMAIL/RUN_TWILIO/RUN_META.")
        return 2

    print(f"Base URL: {base_url}")
    print(f"Channels enabled: widget={run_widget} email={run_email} twilio={run_twilio} meta={run_meta}")
    print(f"History validation: {'ON' if validate_history else 'OFF'}")

    failures: list[str] = []
    warnings: list[str] = []
    passes = 0

    for case in enabled_cases:
        print(f"\n[CASE] {case.id} | kind={case.kind} | lang={case.expected_lang}")

        if case.channel == "widget_chat":
            if not public_client_id:
                failures.append(f"{case.id}: missing WIDGET_PUBLIC_CLIENT_ID")
                print("FAIL missing WIDGET_PUBLIC_CLIENT_ID")
                continue
            ok, detail = _run_widget_case(base_url, case, public_client_id, widget_path)
            expected_provider = "widget"
            expected_channel = "chat"

        elif case.channel == "email_chat":
            if not email_from:
                failures.append(f"{case.id}: missing EMAIL_CHANNEL_ADDRESS")
                print("FAIL missing EMAIL_CHANNEL_ADDRESS")
                continue
            ok, detail = _run_email_case(base_url, case, email_from, email_path, internal_token or "")
            expected_provider = "gmail"
            expected_channel = "email"

        elif case.channel == "twilio_whatsapp":
            ok, detail = _run_twilio_case(base_url, case, twilio_path, twilio_test_user_phone or "+15557654321", twilio_auth_token)
            expected_provider = "twilio"
            expected_channel = "whatsapp"
            if not twilio_auth_token:
                warnings.append("TWILIO_AUTH_TOKEN not set; webhook signature may fail if verification is enabled.")

        elif case.channel == "meta_whatsapp":
            ok, detail = _run_meta_case(
                base_url,
                case,
                meta_path,
                meta_user_phone_digits or "15557654321",
                meta_business_phone_digits or "15551234567",
                meta_app_secret,
            )
            expected_provider = "meta"
            expected_channel = "whatsapp"
            if not meta_app_secret:
                warnings.append("META_APP_SECRET not set; webhook signature may fail if verification is enabled.")
            if ok:
                print("PASS inbound webhook accepted. Confirm outbound WhatsApp message on test handset.")
        else:
            failures.append(f"{case.id}: unknown channel")
            print("FAIL unknown channel")
            continue

        if not ok:
            failures.append(f"{case.id}: {detail}")
            print(f"FAIL {detail}")
            continue

        session_id = detail

        if validate_history:
            history = _history_fetch(base_url, history_client_id or "", session_id, history_bearer or "", history_candidates)
            if not history:
                failures.append(f"{case.id}: history lookup failed for session {session_id}")
                print(f"FAIL history lookup failed ({session_id})")
                continue
            ok_hist, reason = _history_validate(history, case, expected_provider, expected_channel)
            if not ok_hist:
                failures.append(f"{case.id}: history validation failed: {reason}")
                print(f"FAIL history validation: {reason}")
                continue
            print(f"PASS history validated ({session_id})")
        else:
            print(f"PASS basic response validated ({session_id})")

        passes += 1

    print("\n=== Summary ===")
    print(f"Passed: {passes}")
    print(f"Failed: {len(failures)}")
    print(f"Warnings: {len(warnings)}")

    if warnings:
        for w in sorted(set(warnings)):
            print(f"WARN {w}")

    if failures:
        for f in failures:
            print(f"FAIL {f}")
        return 1

    print("All enabled staging smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
