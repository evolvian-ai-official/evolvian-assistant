# Evolvian Admin Tool - Incident Response Runbook (Phase 2)

Date: 2026-02-19
Owner baseline: Security + Backend + Legal

## Purpose

Provide an executable response workflow for security/privacy incidents, including evidence handling and legal notification pathways.

## Severity Classification

| Severity | Example Signal | Initial SLA | Target |
|---|---|---|---|
| Sev-1 | Confirmed unauthorized access/exfiltration of customer data | Immediate page | Active containment in < 1 hour |
| Sev-2 | Suspected breach, strong indicators but not yet confirmed | Immediate triage | Confirm/deny in < 4 hours |
| Sev-3 | Security anomaly without confirmed data impact | Same business day | Resolution or downgrade in < 24 hours |

## Response Workflow

1. Detect and declare incident (`incident_id`, severity, commander).
2. Contain active risk (revoke tokens/keys, isolate endpoints, block abuse vectors).
3. Preserve evidence (logs, snapshots, config, request traces) before destructive cleanup.
4. Scope impact (affected systems, data classes, users, geography).
5. Legal/regulatory decisioning (California + GDPR paths below).
6. Execute notifications if required.
7. Recover and harden (patch, rotate keys, verify no residual access).
8. Postmortem and control updates.

## Notification Decision Baseline

### California (OAG / residents)

- If personal information of California residents is reasonably believed acquired by unauthorized person:
  - Trigger breach-notice process.
  - Use California template: `docs/compliance/templates/incident_notification_california.md`.

### GDPR (EU data subjects)

- If personal data breach is likely to result in risk to rights/freedoms:
  - Notify supervisory authority within 72 hours of awareness.
  - If high risk to data subjects, notify affected individuals without undue delay.
  - Use GDPR template: `docs/compliance/templates/incident_notification_gdpr.md`.

## Evidence Package (Technical)

Minimum artifacts for each incident:

1. `incident_snapshot.json` and `incident_snapshot.md`
2. Current endpoint inventory export
3. Timeline with UTC timestamps of key decisions/actions
4. Secret/key rotation record (if applicable)
5. Affected table/system list and estimated records impacted
6. Internal + external notification drafts/finals

Bundle generation script:

- `python scripts/compliance/generate_incident_evidence_bundle.py`

## Operational Endpoints (Internal)

- `GET /api/internal/compliance/incident/runbook`
- `GET /api/internal/compliance/incident/readiness`

Both require `x-evolvian-internal-token`.

## Tabletop Cadence

- Monthly tabletop mini-drill (30-45 min)
- Quarterly full incident simulation
- Track:
  - time-to-declare
  - time-to-contain
  - time-to-evidence-bundle
  - decision-to-notification elapsed time

