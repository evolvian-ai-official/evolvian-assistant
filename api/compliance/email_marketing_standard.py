from __future__ import annotations

from typing import Iterable

MARKETING_TYPE_KEYWORDS = (
    "marketing",
    "newsletter",
    "campaign",
    "promotional",
    "promo",
    "broadcast",
)

UNSUBSCRIBE_TOKEN = "{{unsubscribe_url}}"
CAMPAIGN_OWNER_TOKEN = "{{campaign_owner_email}}"
POSTAL_ADDRESS_TOKEN = "{{company_postal_address}}"


def is_marketing_template_type(template_type: str | None) -> bool:
    normalized = str(template_type or "").strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in MARKETING_TYPE_KEYWORDS)


def validate_marketing_template_body(body: str | None) -> tuple[bool, list[str]]:
    content = str(body or "")
    required_tokens: Iterable[str] = (
        UNSUBSCRIBE_TOKEN,
        CAMPAIGN_OWNER_TOKEN,
        POSTAL_ADDRESS_TOKEN,
    )
    missing = [token for token in required_tokens if token not in content]
    return not missing, missing


def render_marketing_footer(
    *,
    unsubscribe_url: str,
    campaign_owner_email: str,
    company_postal_address: str,
    support_email: str = "support@evolvianai.com",
) -> str:
    safe_support = support_email.strip() or "support@evolvianai.com"
    safe_owner = campaign_owner_email.strip()
    safe_unsubscribe = unsubscribe_url.strip()
    safe_address = company_postal_address.strip()

    return (
        "<hr style='margin-top:24px;margin-bottom:16px;border:none;border-top:1px solid #d9d9d9;'/>"
        "<p style='font-size:12px;color:#666;line-height:1.5;'>"
        "Campaign owner: "
        f"<a href='mailto:{safe_owner}'>{safe_owner}</a><br/>"
        f"Business address: {safe_address}<br/>"
        f"Questions: <a href='mailto:{safe_support}'>{safe_support}</a><br/>"
        f"Unsubscribe: <a href='{safe_unsubscribe}'>Manage preferences</a>"
        "</p>"
    )


def ensure_marketing_footer(
    *,
    html_body: str,
    unsubscribe_url: str,
    campaign_owner_email: str,
    company_postal_address: str,
    support_email: str = "support@evolvianai.com",
) -> str:
    body = str(html_body or "")
    lower_body = body.lower()
    normalized_unsub = unsubscribe_url.strip().lower()
    normalized_owner = campaign_owner_email.strip().lower()
    normalized_address = company_postal_address.strip().lower()

    has_unsubscribe = normalized_unsub and normalized_unsub in lower_body
    has_owner = normalized_owner and normalized_owner in lower_body
    has_address = normalized_address and normalized_address in lower_body

    if has_unsubscribe and has_owner and has_address:
        return body

    footer = render_marketing_footer(
        unsubscribe_url=unsubscribe_url,
        campaign_owner_email=campaign_owner_email,
        company_postal_address=company_postal_address,
        support_email=support_email,
    )
    return f"{body}\n\n{footer}"
