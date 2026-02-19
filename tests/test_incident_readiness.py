from api.compliance.incident_readiness import (
    incident_secret_checks,
    incident_secret_health,
    render_incident_snapshot_markdown,
)


def test_incident_secret_health_levels(monkeypatch):
    for name in [
        "SUPABASE_SERVICE_ROLE_KEY",
        "EVOLVIAN_INTERNAL_TASK_TOKEN",
        "META_APP_SECRET",
        "TWILIO_AUTH_TOKEN",
        "RESEND_API_KEY",
    ]:
        monkeypatch.setenv(name, "set")

    checks = incident_secret_checks()
    assert incident_secret_health(checks) == "pass"

    monkeypatch.delenv("META_APP_SECRET", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    checks_warn = incident_secret_checks()
    assert incident_secret_health(checks_warn) == "warn"


def test_render_incident_snapshot_markdown_contains_sections():
    snapshot = {
        "snapshot_at": "2026-02-19T13:00:00+00:00",
        "window_hours": 24,
        "secret_health": "warn",
        "secret_checks": [{"env": "META_APP_SECRET", "configured": False}],
        "history_failures": {"scanned_rows": 10, "failed_rows": 2, "failed_by_channel": {"whatsapp": 2}},
        "dsar_overdue": {"open_count": 5, "overdue_count": 1},
    }

    markdown = render_incident_snapshot_markdown(snapshot)
    assert "# Incident Readiness Snapshot" in markdown
    assert "Secret health: warn" in markdown
    assert "whatsapp: 2" in markdown
    assert "Overdue requests: 1" in markdown
