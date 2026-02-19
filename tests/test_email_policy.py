from api.compliance import email_policy


def test_begin_email_send_audit_allows_and_logs_pre_send(monkeypatch):
    logged = []

    def fake_evaluate(**kwargs):
        assert kwargs["channel"] == "email"
        assert kwargs["purpose"] == "marketing"
        return {
            "allowed": True,
            "reason": None,
            "proof_id": "proof_allowed",
            "channel": "email",
            "purpose": "marketing",
        }

    def fake_log(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(email_policy, "evaluate_outbound_policy", fake_evaluate)
    monkeypatch.setattr(email_policy, "log_outbound_policy_event", fake_log)

    allowed, policy = email_policy.begin_email_send_audit(
        client_id="client_1",
        to_email="person@example.com",
        purpose="marketing",
        source="test_source",
        source_id="row_1",
    )

    assert allowed is True
    assert policy["proof_id"] == "proof_allowed"
    assert len(logged) == 1
    assert logged[0]["stage"] == "pre_send"
    assert logged[0]["send_status"] == "allowed_policy"


def test_begin_email_send_audit_blocks_and_logs_reason(monkeypatch):
    logged = []

    def fake_evaluate(**kwargs):
        return {
            "allowed": False,
            "reason": "marketing_opt_out_request_exists",
            "proof_id": "proof_blocked",
            "channel": "email",
            "purpose": "marketing",
        }

    def fake_log(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(email_policy, "evaluate_outbound_policy", fake_evaluate)
    monkeypatch.setattr(email_policy, "log_outbound_policy_event", fake_log)

    allowed, policy = email_policy.begin_email_send_audit(
        client_id="client_1",
        to_email="person@example.com",
        purpose="marketing",
        source="test_source",
    )

    assert allowed is False
    assert policy["proof_id"] == "proof_blocked"
    assert len(logged) == 1
    assert logged[0]["stage"] == "pre_send"
    assert logged[0]["send_status"] == "blocked_policy"
    assert logged[0]["send_error"] == "marketing_opt_out_request_exists"


def test_complete_email_send_audit_logs_success(monkeypatch):
    logged = []

    def fake_log(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(email_policy, "log_outbound_policy_event", fake_log)

    email_policy.complete_email_send_audit(
        client_id="client_1",
        policy_result={"proof_id": "proof_ok"},
        success=True,
        provider_message_id="provider_123",
    )

    assert len(logged) == 1
    assert logged[0]["stage"] == "post_send"
    assert logged[0]["send_status"] == "sent"
    assert logged[0]["provider_message_id"] == "provider_123"


def test_complete_email_send_audit_ignores_missing_policy(monkeypatch):
    logged = []

    def fake_log(**kwargs):
        logged.append(kwargs)

    monkeypatch.setattr(email_policy, "log_outbound_policy_event", fake_log)

    email_policy.complete_email_send_audit(
        client_id="client_1",
        policy_result=None,
        success=False,
        send_error="provider_failed",
    )

    assert logged == []
