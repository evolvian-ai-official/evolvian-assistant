import os
import sys
from urllib.parse import parse_qs, urlparse

from starlette.requests import Request

sys.path.insert(0, os.getcwd())

from api import link_whatsapp as module
from api.security.whatsapp_token_crypto import _get_fernet_optional


def _make_request(host: str = "api.evolvianai.com", scheme: str = "https") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/meta_embedded_signup/start",
        "raw_path": b"/meta_embedded_signup/start",
        "query_string": b"",
        "headers": [
            (b"host", host.encode("utf-8")),
            (b"x-forwarded-host", host.encode("utf-8")),
            (b"x-forwarded-proto", scheme.encode("utf-8")),
        ],
        "scheme": scheme,
        "http_version": "1.1",
        "client": ("127.0.0.1", 54321),
        "server": (host, 443 if scheme == "https" else 80),
    }
    return Request(scope)


def test_normalize_to_e164_accepts_display_phone_format():
    assert module._normalize_to_e164("+52 55 1234 5678") == "+525512345678"
    assert module._normalize_to_e164("525512345678") == "+525512345678"
    assert module._normalize_to_e164("not-a-phone") is None


def test_pick_candidate_phone_prefers_matching_digits():
    candidates = [
        {"phone_id": "a", "display_phone_number": "+1 222 333 4444"},
        {"phone_id": "b", "display_phone_number": "+52 55 1234 5678"},
    ]
    selected = module._pick_candidate_phone(candidates, preferred_phone="+525512345678")
    assert selected["phone_id"] == "b"


def test_append_query_params_replaces_existing_keys():
    base = "https://evolvianai.com/services/meta-apps?meta_setup=old&x=1"
    out = module._append_query_params(base, {"meta_setup": "success", "meta_reason": "ok"})
    parsed = urlparse(out)
    query = parse_qs(parsed.query)
    assert query["meta_setup"] == ["success"]
    assert query["meta_reason"] == ["ok"]
    assert query["x"] == ["1"]


def test_append_fragment_params_replaces_existing_keys():
    base = "https://evolvianai.com/services/meta-apps#meta_setup=old&x=1"
    out = module._append_fragment_params(base, {"meta_setup": "select_phone", "meta_reason": "ok"})
    parsed = urlparse(out)
    fragment = parse_qs(parsed.fragment)
    assert fragment["meta_setup"] == ["select_phone"]
    assert fragment["meta_reason"] == ["ok"]
    assert fragment["x"] == ["1"]


def test_build_meta_oauth_url_contains_expected_query(monkeypatch):
    monkeypatch.setenv("META_APP_ID", "123456")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_GRAPH_VERSION", "v22.0")
    monkeypatch.setenv(
        "META_EMBEDDED_SIGNUP_SCOPES",
        "business_management,whatsapp_business_management,whatsapp_business_messaging",
    )
    request = _make_request()

    url = module._build_meta_oauth_url(request=request, state="state-xyz")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "www.facebook.com"
    assert query["client_id"] == ["123456"]
    assert query["state"] == ["state-xyz"]
    assert query["response_type"] == ["code"]
    assert "whatsapp_business_management" in query["scope"][0]


def test_is_allowed_ui_return_url_accepts_allowed_origin_with_path(monkeypatch):
    monkeypatch.setenv(
        "META_EMBEDDED_ALLOWED_UI_ORIGINS",
        "https://evolvianai.com/services/meta-apps",
    )
    assert module._is_allowed_ui_return_url("https://evolvianai.com/services/meta-apps")
    assert module._is_allowed_ui_return_url("https://evolvianai.com/otra-ruta")


def test_is_allowed_ui_return_url_supports_host_only_entry(monkeypatch):
    monkeypatch.setenv("META_EMBEDDED_ALLOWED_UI_ORIGINS", "evolvianai.com")
    assert module._is_allowed_ui_return_url("https://evolvianai.com/services/meta-apps")
    assert not module._is_allowed_ui_return_url("https://evil.example.com/services/meta-apps")


def test_pick_matching_candidate_phone_requires_preferred_phone():
    candidates = [
        {"phone_id": "a", "display_phone_number": "+1 222 333 4444"},
        {"phone_id": "b", "display_phone_number": "+52 55 1234 5678"},
    ]
    assert module._pick_matching_candidate_phone(candidates, preferred_phone="") is None
    selected = module._pick_matching_candidate_phone(candidates, preferred_phone="+525512345678")
    assert selected["phone_id"] == "b"


def test_selection_token_roundtrip(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN_ENCRYPTION_KEY", "test-meta-selection-secret")
    _get_fernet_optional.cache_clear()
    try:
        token = module._encode_selection_token(
            client_id="client_1",
            wa_token="EAATOKEN123",
            preferred_phone="+525512345678",
            candidates=[
                {
                    "phone_id": "111",
                    "waba_id": "999",
                    "display_phone_number": "+52 55 1234 5678",
                    "verified_name": "Evolvian",
                }
            ],
        )
        decoded = module._decode_selection_token(token, max_age_seconds=1200)
        assert decoded["client_id"] == "client_1"
        assert decoded["wa_token"] == "EAATOKEN123"
        assert decoded["candidates"][0]["phone_id"] == "111"
    finally:
        _get_fernet_optional.cache_clear()
