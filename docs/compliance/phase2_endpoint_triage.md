# Evolvian Admin Tool - Endpoint Triage (Phase 2)

Date: 2026-02-19
Source: `docs/compliance/endpoint_control_inventory.csv` (105 endpoints)

## Snapshot

- `review_required`: 0 endpoints
- Categories:
  - Active + real risk: 0
  - Active + public/business-justified: 6
  - Legacy/unmounted endpoint debt: 0

## Mitigated in This Implementation

| Status | Endpoint | Evidence | Mitigation |
|---|---|---|---|
| Closed (P0) | `POST /create_appointment` | `api/appointments/create_appointment.py:1162` | Requires tenant ownership via bearer token, with internal-token bypass for trusted automation. |
| Closed (P0) | `POST /gmail_poll/check` | `api/modules/email_integration/gmail_poll.py:146` | Requires internal request token. |
| Closed (P0) | `GET /get_client_by_email` | `api/modules/assistant_rag/get_client_by_email.py:11` | Requires internal request token; prevents tenant/email enumeration from public surface. |
| Closed (P1) | `POST /ask` | `api/ask_question_api.py:45` | Requires tenant ownership via bearer token or internal-token bypass. |
| Closed (P1) | `POST /calendar/book` | `api/calendar_routes.py:22` | Requires tenant ownership via bearer token or internal-token bypass. |
| Closed (P1) | `POST /chat_email` | `api/modules/assistant_rag/chat_email.py:149` | HTTP route requires internal token; Gmail webhook path uses internal helper directly. |
| Closed (P1) | `POST /appointments/reminders/{reminder_id}/send-meta` | `api/appointments/meta_reminder.py:53` | Requires internal request token. |
| Closed (P2) | `POST /api/whatsapp/send_reminder` | `api/modules/whatsapp/send_reminder.py:13` | Requires internal request token. |
| Closed (P2) | Legacy duplicate endpoints removed | `api/accept_terms_api.py`, `api/stripe_create_checkout_session.py`, `api/link_channel.py`, `api/api:twilio_webhook.py` | Deleted dead insecure variants to avoid accidental re-exposure. |
| Closed (P2) | Unmounted route decorators removed | `api/modules/calendar/schedule_event.py`, `api/modules/email_integration/gmail_setup_watch.py` | Converted to internal helpers (no exposed route decorators). |
| Closed (P0) | DSAR internal operations endpoints | `api/internal/privacy_requests.py:114`, `api/internal/privacy_requests.py:162`, `api/internal/privacy_requests.py:253` | Internal-only DSAR list/update/metrics routes require internal token and enforce status-transition workflow. |
| Closed (P1) | Retention operations endpoints | `api/internal/retention_jobs.py:33`, `api/internal/retention_jobs.py:46` | Internal-only retention rules/run endpoints require internal token; apply mode is gated by explicit confirmation + env flag. |
| Closed (P1) | Incident readiness endpoints | `api/internal/incident_readiness.py:18`, `api/internal/incident_readiness.py:32` | Internal-only incident runbook/readiness snapshot routes require internal token and expose no public attack surface. |

## Active + Public/Business-Justified

| Priority | Endpoint | Evidence | Notes |
|---|---|---|---|
| P2 | `POST /chat` | `api/chat_widget_api.py:609` | Public widget surface; now includes in-process rate limits by IP and session (`chat_widget_ip`, `chat_widget_session`). |
| P2 | `GET /check_consent` | `api/check_consent.py:21` | Public consent-status endpoint; now includes IP/client rate limiting (`check_consent_ip`). |
| P2 | `POST /register_consent` | `api/register_consent.py:28` | Public consent capture; now includes IP/client rate limiting (`register_consent_ip`). |
| P2 | `GET /meta_approved_templates` | `api/templates/meta_approved_templates.py:35` | Public read-only templates endpoint; now includes IP rate limiting (`meta_templates_ip`). |
| P2 | `POST /api/public/privacy/request` | `api/public/privacy.py:76` | Public DSAR intake endpoint; now includes IP rate limiting (`privacy_request_ip`) and generated DSAR ticket/deadline metadata. |
| P2 | `GET /api/public/privacy/request/status` | `api/public/privacy.py:170` | Public DSAR status lookup (email + request_id) with IP rate limiting (`privacy_request_status_ip`). |

## Notes

- Current rate limiting is in-process memory based (`api/security/request_limiter.py`): good baseline but not globally shared across instances.
- Recommended next hardening: centralized/distributed rate limiting at edge or shared store (e.g., Cloudflare/WAF, Redis, API gateway).
- DSAR state and SLA metadata are now captured in `api/public/privacy.py` and operated via internal workflow routes in `api/internal/privacy_requests.py`.
