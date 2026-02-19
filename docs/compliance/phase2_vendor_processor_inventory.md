# Evolvian Admin Tool - Vendor / Processor Inventory (Phase 2)

Date: 2026-02-19
Scope: Backend services and processors observed in current code paths.

## Purpose

Provide an auditable inventory of subprocessors/service providers used by Evolvian systems, with DPA/SCC tracking fields and a repeatable evidence baseline.

## Vendor Inventory

| Vendor | Role | Primary Purpose | Data Categories (High Level) | Regions / Transfer Risk | DPA Status | SCC / Transfer Mechanism | Technical Evidence |
|---|---|---|---|---|---|---|---|
| Supabase | Processor / Service Provider | Primary database, auth metadata, storage, event logs | Account identifiers, contact data, consent records, appointments, DSAR tickets, logs | US-hosted deployment expected; verify project region and transfer mapping | Pending legal confirmation | Pending legal confirmation | `api/config/config.py`, `api/modules/assistant_rag/supabase_client.py` |
| OpenAI | Subprocessor | LLM inference for assistant features | User prompts, contextual excerpts, metadata required to answer | Cross-border transfer possible depending routing/model configuration | Pending legal confirmation | Pending legal confirmation | `api/modules/assistant_rag/llm.py`, `api/modules/assistant_rag/rag_pipeline.py` |
| Stripe | Processor / Service Provider | Payments, subscription lifecycle, webhook events | Billing identifiers, subscription metadata, transaction state | US/global processing; verify applicable transfer terms | Pending legal confirmation | Pending legal confirmation | `api/stripe_webhook.py`, `api/create_checkout_session.py`, `api/utils/stripe_plan_utils.py` |
| Twilio | Processor / Service Provider | Messaging webhook processing (SMS/WhatsApp legacy path) | Phone numbers, message metadata, delivery events | Cross-border transfer possible | Pending legal confirmation | Pending legal confirmation | `api/twilio_webhook.py`, `api/webhook_security.py` |
| Meta (WhatsApp Cloud API) | Processor / Service Provider | WhatsApp outbound/inbound messaging | Phone numbers, message content/templates, delivery status | Cross-border transfer possible | Pending legal confirmation | Pending legal confirmation | `api/modules/whatsapp/whatsapp_sender.py`, `api/meta_webhook.py` |
| Google (Gmail/Calendar APIs) | Processor / Service Provider | OAuth integrations, calendar sync, email send/receive | Email addresses, message content, calendar availability and events | Cross-border transfer possible | Pending legal confirmation | Pending legal confirmation | `api/modules/email_integration/gmail_oauth.py`, `api/calendar_routes.py`, `api/modules/calendar/schedule_event.py` |
| Resend | Subprocessor | Transactional email delivery (confirmation/notifications) | Recipient email, message content, template metadata | Cross-border transfer possible | Pending legal confirmation | Pending legal confirmation | `api/modules/calendar/send_confirmation_email.py`, `api/modules/calendar/notify_business_owner.py` |
| SendGrid (legacy/optional) | Subprocessor | Legacy fallback email delivery in schedule flow | Recipient email, message content | Cross-border transfer possible | Pending legal confirmation | Pending legal confirmation | `api/modules/calendar/schedule_event.py` |
| Render | Infrastructure provider | Application hosting/runtime | Application logs, runtime metadata, environment-scoped processing | US-hosted service expected | Pending legal confirmation | N/A (controller-to-processor terms by contract) | `api/config/config.py`, deployment env references |

## Data-Flow Baseline (Technical)

1. User channels (`web chat`, `email`, `WhatsApp`, `public forms`) send payloads to Evolvian API.
2. Evolvian persists operational records in Supabase (`history`, `appointments`, `public_privacy_requests`, consent tables).
3. Evolvian exchanges operational events with processors:
   - Billing: Stripe
   - Messaging: Meta/Twilio
   - Email: Gmail APIs, Resend, optional SendGrid
   - LLM inference: OpenAI
4. Audit events for outbound policy are stored in `history` with `source_type=compliance_outbound_policy` and `proof_id`.

## Evidence and Review Cadence

- Source of truth table: `docs/compliance/vendor_processor_inventory.csv`
- Snapshot automation: `scripts/compliance/generate_vendor_inventory_snapshot.py`
- Evidence output folder: `docs/compliance/evidence/YYYY-MM/`
- Review frequency: monthly (Legal + Security + Backend owner)

## Remaining Actions to Reach Full Vendor Governance

- Attach signed DPA files and current URLs/versions for each vendor.
- Record SCC/transfer mechanism determination per vendor jurisdiction.
- Add contract renewal dates and last legal review date per vendor.
- Link each vendor to a system owner and on-call contact.
