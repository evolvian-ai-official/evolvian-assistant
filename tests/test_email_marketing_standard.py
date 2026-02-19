from api.compliance.email_marketing_standard import (
    CAMPAIGN_OWNER_TOKEN,
    POSTAL_ADDRESS_TOKEN,
    UNSUBSCRIBE_TOKEN,
    ensure_marketing_footer,
    is_marketing_template_type,
    validate_marketing_template_body,
)


def test_marketing_type_detection():
    assert is_marketing_template_type("newsletter") is True
    assert is_marketing_template_type("campaign_email") is True
    assert is_marketing_template_type("appointment_confirmation") is False


def test_validate_marketing_template_body_requires_tokens():
    body = f"<p>Hello</p>{UNSUBSCRIBE_TOKEN}{CAMPAIGN_OWNER_TOKEN}{POSTAL_ADDRESS_TOKEN}"
    ok, missing = validate_marketing_template_body(body)
    assert ok is True
    assert missing == []

    broken = "<p>Hello</p>"
    ok2, missing2 = validate_marketing_template_body(broken)
    assert ok2 is False
    assert UNSUBSCRIBE_TOKEN in missing2
    assert CAMPAIGN_OWNER_TOKEN in missing2
    assert POSTAL_ADDRESS_TOKEN in missing2


def test_ensure_marketing_footer_appends_when_missing():
    html = "<p>Promo message</p>"
    updated = ensure_marketing_footer(
        html_body=html,
        unsubscribe_url="https://example.com/unsubscribe?u=1",
        campaign_owner_email="owner@example.com",
        company_postal_address="123 Main St, City, Country",
    )
    assert "unsubscribe" in updated.lower()
    assert "owner@example.com" in updated
    assert "123 Main St, City, Country" in updated


def test_ensure_marketing_footer_is_idempotent_when_present():
    html = (
        "<p>Promo message</p>"
        "<p>Campaign owner: owner@example.com</p>"
        "<p>Business address: 123 Main St, City, Country</p>"
        "<p><a href='https://example.com/unsubscribe?u=1'>Unsubscribe</a></p>"
    )
    updated = ensure_marketing_footer(
        html_body=html,
        unsubscribe_url="https://example.com/unsubscribe?u=1",
        campaign_owner_email="owner@example.com",
        company_postal_address="123 Main St, City, Country",
    )
    assert updated == html
