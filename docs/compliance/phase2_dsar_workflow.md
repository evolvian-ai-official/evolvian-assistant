# Evolvian Admin Tool - DSAR Workflow Baseline (Phase 2)

Date: 2026-02-19

## Purpose

Provide an auditable technical flow for privacy rights requests (access, delete, correct, opt-out) aligned to CCPA/CPRA operational expectations.

## Implemented Endpoints

- Public intake: `POST /api/public/privacy/request` (`api/public/privacy.py:76`)
- Public status lookup: `GET /api/public/privacy/request/status` (`api/public/privacy.py:170`)
- Internal queue/list: `GET /api/internal/privacy/requests` (`api/internal/privacy_requests.py:114`)
- Internal update/state transition: `PATCH /api/internal/privacy/requests/{request_id}` (`api/internal/privacy_requests.py:162`)
- Internal KPI snapshot: `GET /api/internal/privacy/metrics` (`api/internal/privacy_requests.py:253`)

Internal endpoints require `x-evolvian-internal-token` via `require_internal_request`.

## Request Lifecycle

1. Intake creates a DSAR `request_id` and records request metadata.
2. Initial status is `pending`.
3. Internal operators move state through validation/fulfillment.
4. Terminal states: `fulfilled`, `denied`, `withdrawn`.

State transitions are enforced in `api/privacy_dsr.py` (`is_valid_status_transition`).

## SLA Rules

- Baseline due date: `submitted_at + 45 days`.
- Optional extension: up to `+45 days` when justified.
- Due-date calculation lives in `api/privacy_dsr.py` (`calculate_due_at`).
- Metrics endpoint reports open/overdue/closed and on-time completion rate.

## Audit Trail

- Each request stores metadata events (`submitted`, `internal_update`, etc.) in structured DSAR metadata.
- Internal updates append event records with timestamp and operator action summary.
- Metrics snapshots can be exported monthly for evidence packs.

## Current Gaps (Open)

- Identity verification SOP and evidence checklist are not yet formalized.
- Automated overdue alerting/escalation (cron + notification) is not yet configured.
- Metadata currently persists inside request details payload; dedicated normalized DSAR tables are recommended for long-term reporting.
