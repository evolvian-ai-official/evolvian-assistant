# Evolvian Admin Tool - Retention Matrix Baseline (Phase 2)

Date: 2026-02-19

## Objective

Define and operationalize a table-level retention baseline to reduce over-retention risk and support storage limitation obligations.

## Technical Controls Implemented

- Retention policy engine: `api/compliance/retention_policy.py`
- Internal retention endpoints (token-protected):
  - `GET /api/internal/compliance/retention/rules`
  - `POST /api/internal/compliance/retention/run`
  - Router: `api/internal/retention_jobs.py`
- Runtime safety controls:
  - Dry-run default
  - Apply mode requires both:
    - `confirmation=APPLY_RETENTION_JOB`
    - env `EVOLVIAN_RETENTION_ALLOW_APPLY=true`

## Retention Rules (Baseline)

| Table | Date Column | Retention (days) | Action | Rationale |
|---|---|---:|---|---|
| `history` | `created_at` | 365 | anonymize | Keep operational telemetry while redacting message content and metadata payload. |
| `public_privacy_requests` | `created_at` | 1095 | delete | DSAR/privacy requests retained for auditable period then removed. |
| `public_privacy_consents` | `created_at` | 1095 | delete | Public privacy consent logs retained for audit window. |
| `widget_consents` | `consent_at` | 1095 | delete | Widget consent records retained for compliance evidence window. |
| `appointment_usage` | `created_at` | 730 | delete | Operational usage events retained for trend/audit, then removed. |
| `appointment_reminders` | `created_at` | 730 | delete | Reminder execution data retained for troubleshooting period. |

## Execution Guidance

1. Run dry-run first:
   - `POST /api/internal/compliance/retention/run` with `{ "apply": false }`
2. Review candidate counts and errors.
3. Enable apply only in controlled maintenance windows.
4. Run apply with explicit confirmation:
   - `{ "apply": true, "confirmation": "APPLY_RETENTION_JOB" }`

## Remaining Gaps

- Rules are baseline and should be validated with legal/data owners before production apply.
- Some non-core datasets may still require additional retention definitions.
- Scheduling/automation cadence for retention execution should be formalized (e.g., monthly).
