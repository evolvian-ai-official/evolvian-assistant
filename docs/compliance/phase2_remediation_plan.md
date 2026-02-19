# Evolvian Admin Tool - Compliance Remediation Plan (30-60-90)

Date: 2026-02-19

## Objective

Reach "compliance-ready" posture for legal due diligence and lower regulatory/litigation risk by closing high-risk technical exposure and formalizing operational controls.

## Progress Update (2026-02-19)

- Completed: `POST /create_appointment` now enforces tenant ownership or internal token.
- Completed: `POST /gmail_poll/check` now requires internal request token.
- Completed: `GET /get_client_by_email` now requires internal request token.
- Completed: `POST /ask` now enforces tenant ownership or internal token.
- Completed: `POST /calendar/book` now enforces tenant ownership or internal token.
- Completed: `POST /chat_email` now requires internal request token; Gmail webhook now uses internal helper flow.
- Completed: `POST /appointments/reminders/{reminder_id}/send-meta` now requires internal request token.
- Completed: `POST /api/whatsapp/send_reminder` now requires internal request token.
- Completed: legal contact email normalized to `support@evolvianai.com` in client uploader legal pages.
- Completed: legacy duplicate endpoint files removed (`accept_terms_api`, `stripe_create_checkout_session`, `link_channel`, legacy `api:twilio_webhook`).
- Completed: unmounted route decorators removed from `schedule_event` and `gmail_setup_watch` modules.
- Completed: anti-abuse rate limiting added to public endpoints (`/chat`, `/check_consent`, `/register_consent`, `/meta_approved_templates`).
- Completed baseline: DSAR workflow shipped with ticket IDs, status machine, deadline calculator, internal operations endpoints, and metrics (`api/public/privacy.py`, `api/internal/privacy_requests.py`, `api/privacy_dsr.py`).
- Completed baseline: centralized outbound policy engine for WhatsApp template/text sends with consent + opt-out enforcement and auditable `proof_id` events (`api/compliance/outbound_policy.py`, `api/modules/whatsapp/whatsapp_sender.py`).
- Completed baseline: email outbound sender paths now use centralized policy/audit hooks (`api/compliance/email_policy.py`, `api/modules/calendar/send_confirmation_email.py`, `api/modules/email_integration/gmail_oauth.py`) with pre-send blocking + post-send evidence logging.
- Completed baseline: retention policy engine + internal dry-run/apply retention jobs with safety guards (`api/compliance/retention_policy.py`, `api/internal/retention_jobs.py`).
- Completed baseline: incident runbook + notification templates + internal readiness snapshot endpoints + evidence bundle generator (`docs/compliance/phase2_incident_runbook.md`, `api/internal/incident_readiness.py`, `scripts/compliance/generate_incident_evidence_bundle.py`).
- Completed baseline: vendor/processor inventory + data-flow mapping + evidence snapshot script (`docs/compliance/phase2_vendor_processor_inventory.md`, `docs/compliance/vendor_processor_inventory.csv`, `scripts/compliance/generate_vendor_inventory_snapshot.py`).
- Completed baseline: outbound policy guardrail tests for critical email/WhatsApp sender entrypoints (`tests/test_outbound_guardrails.py`).
- Completed baseline: outbound guardrail tests wired into CI (`.github/workflows/outbound-guardrails.yml`).
- Completed baseline: marketing email technical standards enforced (required tokens in templates + required campaign ownership/unsubscribe metadata in marketing sends) (`api/compliance/email_marketing_standard.py`, `api/appointments/message_templates.py`, `api/modules/email_integration/gmail_oauth.py`).

## 0-30 Days (Critical Hardening)

| Priority | Workstream | Deliverable | Owner |
|---|---|---|---|
| P0 | Internal endpoint protection | Completed baseline: internal token required on cron/automation endpoints identified in triage. | Backend |
| P0 | Tenant boundary enforcement | Completed baseline: `POST /create_appointment`, `POST /ask`, `POST /calendar/book` now enforce ownership or internal token. | Backend |
| P0 | Remove legacy attack surface | Completed: duplicate/unmounted legacy routes/files removed or neutralized. | Backend |
| P1 | Abuse controls on public endpoints | Completed baseline: in-process rate limiting on public chat/consent/template endpoints; edge/shared limiter still pending. | Backend + Frontend |
| P1 | Legal consistency fix | Completed in source: legal contact email standardized across Terms/Privacy pages. | Legal + Frontend |
| P1 | Production secret enforcement | Startup fail-fast checks for webhook secrets/tokens in production (`TWILIO_AUTH_TOKEN`, `META_APP_SECRET`, internal task token). | Platform |

## 31-60 Days (Legal Operations)

| Priority | Workstream | Deliverable | Owner |
|---|---|---|---|
| P0 | DSAR operations | Completed baseline in code: intake + status lookup + internal list/update/metrics with 45-day SLA timer. Remaining: formal identity verification SOP and automated escalation alerts. | Legal Ops + Backend |
| P1 | Consent governance | Baseline shipped for WhatsApp + current email sender paths with centralized policy checks + proof logs, static guardrail tests in CI, and marketing template/send standards. Remaining: operational owner approval workflow evidence and recurring campaign QA sampling. | Backend |
| P1 | Retention controls | Baseline shipped: table-level retention matrix + internal purge/anonymization job endpoint with apply guardrails. Remaining: legal sign-off on retention windows and scheduled execution cadence. | Data + Backend |
| P1 | Vendor governance | Baseline inventory/data-flow package shipped; remaining: attach signed DPA/SCC legal artifacts and monthly review sign-off records. | Legal + Security |

## 61-90 Days (Audit Readiness)

| Priority | Workstream | Deliverable | Owner |
|---|---|---|---|
| P1 | Incident readiness | Baseline shipped: runbook + California/GDPR templates + internal readiness snapshot and evidence bundle generation. Remaining: recurring tabletop drill records. | Security + Legal |
| P1 | Evidence automation | Monthly control evidence bundle generated from code/config/log exports. | Security + Platform |
| P2 | External legal validation | Counsel review of Terms/Privacy + consent language + DSAR process. | Legal |
| P2 | Control testing | Quarterly access-control and webhook-signature test cases in CI. | QA + Backend |

## Exit Criteria (Compliance-Ready Baseline)

- No P0 endpoint risks remain open.
- DSAR and consent workflows are operational with auditable logs.
- Incident response runbook approved and tested.
- Vendor/DPA inventory complete and current.
- Public legal pages are consistent and versioned.

## Tracking KPIs

- `P0_open_count` (target: 0)
- `% internal endpoints with token guard` (target: 100%)
- `DSAR on-time completion rate` (target: >= 99%)
- `% outbound campaigns with consent proof attached` (target: 100%)
- `mean incident evidence collection time` (target: < 24h)
