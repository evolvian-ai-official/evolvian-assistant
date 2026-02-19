from __future__ import annotations

import logging
from typing import Any

from api.compliance.outbound_policy import (
    evaluate_outbound_policy,
    log_outbound_policy_event,
)

logger = logging.getLogger(__name__)


def begin_email_send_audit(
    *,
    client_id: str,
    to_email: str,
    purpose: str = "transactional",
    source: str,
    source_id: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    policy = evaluate_outbound_policy(
        client_id=client_id,
        channel="email",
        purpose=purpose,
        recipient_email=to_email,
        source=source,
        source_id=source_id,
    )

    if not policy.get("allowed"):
        log_outbound_policy_event(
            client_id=client_id,
            policy_result=policy,
            stage="pre_send",
            send_status="blocked_policy",
            send_error=str(policy.get("reason") or "policy_blocked"),
        )
        logger.warning(
            "⛔ Email blocked by outbound policy | client_id=%s | to=%s | purpose=%s | reason=%s | proof_id=%s",
            client_id,
            to_email,
            purpose,
            policy.get("reason"),
            policy.get("proof_id"),
        )
        return False, policy

    log_outbound_policy_event(
        client_id=client_id,
        policy_result=policy,
        stage="pre_send",
        send_status="allowed_policy",
    )
    return True, policy


def complete_email_send_audit(
    *,
    client_id: str,
    policy_result: dict[str, Any] | None,
    success: bool,
    provider_message_id: str | None = None,
    send_error: str | None = None,
) -> None:
    if not policy_result:
        return

    log_outbound_policy_event(
        client_id=client_id,
        policy_result=policy_result,
        stage="post_send",
        send_status="sent" if success else "failed",
        provider_message_id=provider_message_id,
        send_error=send_error,
    )
