from datetime import datetime, timedelta, timezone

from api.compliance.outbound_policy import (
    ConsentSnapshot,
    PolicySettings,
    evaluate_policy_decision,
)


def _settings(**overrides):
    base = PolicySettings(
        require_email_consent=False,
        require_phone_consent=False,
        require_terms_consent=False,
        consent_renewal_days=90,
        require_reminder_consent=True,
        require_marketing_opt_in=True,
        allow_transactional_without_consent=True,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _consent(**overrides):
    base = ConsentSnapshot(
        consent_id="cons_123",
        consent_at=datetime.now(timezone.utc) - timedelta(days=2),
        accepted_terms=True,
        accepted_email_marketing=True,
        email_present=True,
        phone_present=True,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_marketing_email_requires_opt_in():
    now = datetime.now(timezone.utc)
    allowed, reason, _ = evaluate_policy_decision(
        channel="email",
        purpose="marketing",
        settings=_settings(),
        consent=_consent(accepted_email_marketing=False),
        opt_out=None,
        recipient_email="test@example.com",
        recipient_phone=None,
        now=now,
    )
    assert allowed is False
    assert reason == "email_marketing_not_opted_in"


def test_marketing_email_blocks_opt_out_request():
    now = datetime.now(timezone.utc)
    allowed, reason, _ = evaluate_policy_decision(
        channel="email",
        purpose="marketing",
        settings=_settings(),
        consent=_consent(),
        opt_out={"id": "dsar-1", "status": "pending"},
        recipient_email="test@example.com",
        recipient_phone=None,
        now=now,
    )
    assert allowed is False
    assert reason == "marketing_opt_out_request_exists"


def test_reminder_requires_fresh_consent_when_strict():
    now = datetime.now(timezone.utc)
    old_consent = _consent(consent_at=now - timedelta(days=150))
    allowed, reason, _ = evaluate_policy_decision(
        channel="whatsapp",
        purpose="reminder",
        settings=_settings(require_reminder_consent=True),
        consent=old_consent,
        opt_out=None,
        recipient_email=None,
        recipient_phone="+15550001111",
        now=now,
    )
    assert allowed is False
    assert reason == "missing_or_expired_reminder_consent"


def test_reminder_can_pass_when_strict_disabled():
    now = datetime.now(timezone.utc)
    allowed, reason, _ = evaluate_policy_decision(
        channel="whatsapp",
        purpose="reminder",
        settings=_settings(require_reminder_consent=False),
        consent=_consent(consent_id=None, consent_at=None, accepted_terms=False, phone_present=False),
        opt_out=None,
        recipient_email=None,
        recipient_phone="+15550001111",
        now=now,
    )
    assert allowed is True
    assert reason is None


def test_transactional_allows_without_consent_by_default():
    now = datetime.now(timezone.utc)
    allowed, reason, _ = evaluate_policy_decision(
        channel="whatsapp",
        purpose="transactional",
        settings=_settings(allow_transactional_without_consent=True),
        consent=_consent(consent_id=None, consent_at=None, accepted_terms=False, phone_present=False),
        opt_out=None,
        recipient_email=None,
        recipient_phone="+15550001111",
        now=now,
    )
    assert allowed is True
    assert reason is None
