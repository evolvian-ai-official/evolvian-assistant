# Evolvian Admin Tool - Audit Evidence Checklist

Date: 2026-02-19
Purpose: repeatable evidence package for legal/security due diligence.

## A. Governance and Policy Evidence

- [ ] Current Terms of Service (version, effective date, changelog).
- [ ] Current Privacy Policy (version, effective date, changelog).
- [ ] Legal contact channels consistent across all user surfaces.
- [ ] Data retention and deletion policy approved (baseline matrix + job implemented, pending legal approval).
- [x] Incident response runbook + breach notification templates baseline implemented.
- [x] Vendor inventory/data-flow baseline (`docs/compliance/phase2_vendor_processor_inventory.md`, `docs/compliance/vendor_processor_inventory.csv`).
- [ ] Signed DPA/SCC artifact links and legal review sign-off per active vendor.

## B. Access Control Evidence

- [ ] Endpoint inventory export: `docs/compliance/endpoint_control_inventory.csv`.
- [ ] Endpoint risk triage: `docs/compliance/phase2_endpoint_triage.md`.
- [ ] Proof that all internal/cron endpoints require internal token.
- [ ] Proof that tenant-sensitive endpoints enforce ownership/auth.
- [ ] CI/test evidence for auth guard regressions.

## C. Consent and Communications Evidence

- [ ] Consent capture payload schema (fields: timestamp, IP, user-agent, subject identifiers).
- [ ] Consent validation logic and expiry rules.
- [x] Unsubscribe/suppression list controls baseline for current email sender paths (policy pre-send block + post-send audit in `api/compliance/email_policy.py` and sender integrations).
- [x] Opt-in/consent proof linkage baseline for WhatsApp outbound wrappers (`api/compliance/outbound_policy.py` + history `proof_id` events).
- [x] Static guardrail tests for outbound sender wrappers (`tests/test_outbound_guardrails.py`).
- [x] CI workflow enforcing outbound guardrails (`.github/workflows/outbound-guardrails.yml`).
- [x] Marketing template/send technical standards enforced (`api/compliance/email_marketing_standard.py`, `api/appointments/message_templates.py`, `api/modules/email_integration/gmail_oauth.py`).
- [ ] Message template approval process and ownership controls.

## D. Security Operations Evidence

- [ ] Production secret management inventory (webhook and internal tokens).
- [ ] Webhook signature verification tests (Meta/Twilio/Gmail if applicable).
- [ ] Public endpoint rate-limit policy + evidence (scope, thresholds, and logs).
- [x] Retention run controls implemented (dry-run/apply guard + internal token + confirmation gate).
- [ ] Logging and monitoring runbook for suspicious endpoint activity.
- [ ] Incident drill/tabletop records and postmortems.
- [x] Breach notification template package (California and GDPR paths).

## E. Data Subject Request (DSAR) Evidence

- [x] Intake channel(s) defined and publicly documented (`POST /api/public/privacy/request`, `GET /api/public/privacy/request/status`).
- [ ] Identity verification standard for requests.
- [x] Workflow state machine (received, verified, in progress, completed, rejected) with transition checks (`api/privacy_dsr.py` + `PATCH /api/internal/privacy/requests/{request_id}`).
- [ ] SLA timers and escalation alerts.
- [x] Completion logs with timestamps and outcome artifacts (DSAR metadata events in `details` + `/api/internal/privacy/metrics` snapshot).

## F. Recommended Monthly Cadence

- [ ] Regenerate endpoint inventory and compare deltas.
- [ ] Re-run endpoint triage and close newly exposed risks.
- [ ] Sample 5 consent records and 5 outbound communications for consent-proof checks.
- [x] Run outbound guardrail test suite (`PYTHONPATH=. pytest -q tests/test_outbound_guardrails.py`).
- [ ] Validate legal page consistency and contact info.
- [ ] Confirm vendor/DPA inventory freshness.

## Evidence Package (Suggested Folder)

- `docs/compliance/evidence/YYYY-MM/`
- Minimum contents:
  - `endpoint_control_inventory.csv`
  - `endpoint_triage.md`
  - `dsar_metrics.csv`
  - `incident_snapshot.json`
  - `incident_snapshot.md`
  - `consent_sampling_report.md`
  - `incident_readiness_checklist.md`
  - `vendor_inventory_snapshot.json`
  - `vendor_inventory_snapshot.md`
