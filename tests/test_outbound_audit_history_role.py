def test_log_outbound_policy_event_falls_back_from_invalid_role(monkeypatch):
    from api.compliance import outbound_policy

    state = {
        "attempted_roles": [],
    }

    class _FakeTable:
        def __init__(self):
            self._payload = None

        def insert(self, payload):
            self._payload = payload
            return self

        def execute(self):
            role = str((self._payload or {}).get("role") or "")
            state["attempted_roles"].append(role)
            if role == "system":
                raise Exception(
                    'new row for relation "history" violates check constraint "history_role_check"'
                )
            return type("Response", (), {"data": [self._payload]})()

    class _FakeSupabase:
        def table(self, table_name: str):
            assert table_name == "history"
            return _FakeTable()

    monkeypatch.setattr(outbound_policy, "supabase", _FakeSupabase())
    monkeypatch.setenv("EVOLVIAN_HISTORY_AUDIT_ROLE", "system")

    outbound_policy.log_outbound_policy_event(
        client_id="client_1",
        policy_result={
            "proof_id": "proof_123",
            "channel": "email",
            "purpose": "transactional",
            "allowed": True,
            "source_id": "row_1",
        },
        stage="pre_send",
        send_status="allowed_policy",
    )

    assert state["attempted_roles"][:2] == ["system", "assistant"]


def test_send_confirmation_email_defaults_to_transactional(monkeypatch):
    from api.modules.calendar import send_confirmation_email as module

    captured = {}

    def fake_begin_email_send_audit(**kwargs):
        captured["purpose"] = kwargs.get("purpose")
        return False, {"reason": "blocked_for_test", "proof_id": "proof_x"}

    monkeypatch.setattr(module, "begin_email_send_audit", fake_begin_email_send_audit)

    result = module.send_confirmation_email(
        to_email="person@example.com",
        date_str="2026-02-19",
        hour_str="10:30",
        html_body="<p>test</p>",
        subject="Test",
        client_id="client_1",
        user_name="Person",
        appointment_type="demo",
    )

    assert result is False
    assert captured["purpose"] == "transactional"
