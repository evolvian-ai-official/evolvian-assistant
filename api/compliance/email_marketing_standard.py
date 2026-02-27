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
MARKETING_FOOTER_MARKER = "<!--EVOLVIAN_MARKETING_FOOTER-->"


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
) -> str:
    safe_owner = campaign_owner_email.strip()
    safe_unsubscribe = unsubscribe_url.strip()
    safe_address = company_postal_address.strip()

    return (
        f"{MARKETING_FOOTER_MARKER}"
        "<hr style='margin-top:24px;margin-bottom:16px;border:none;border-top:1px solid #d9d9d9;'/>"
        "<p style='font-size:12px;color:#666;line-height:1.5;'>"
        "Campaign owner: "
        f"<a href='mailto:{safe_owner}'>{safe_owner}</a><br/>"
        f"Business address: {safe_address}<br/>"
        f"Unsubscribe: <a href='{safe_unsubscribe}'>Opt out of marketing emails</a>"
        "</p>"
    )


def ensure_marketing_footer(
    *,
    html_body: str,
    unsubscribe_url: str,
    campaign_owner_email: str,
    company_postal_address: str,
) -> str:
    body = str(html_body or "")
    if MARKETING_FOOTER_MARKER in body:
        return body

    footer = render_marketing_footer(
        unsubscribe_url=unsubscribe_url,
        campaign_owner_email=campaign_owner_email,
        company_postal_address=company_postal_address,
    )
    return f"{body}\n\n{footer}"
