from starlette.requests import Request

from api.modules.email_integration.gmail_oauth import _resolve_gmail_redirect_uri


def _make_request(host: str, scheme: str = "https") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/gmail_oauth/authorize",
        "raw_path": b"/gmail_oauth/authorize",
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


def test_gmail_redirect_uri_prefers_matching_prod_host(monkeypatch):
    monkeypatch.setenv("GMAIL_REDIRECT_URI_LOCAL", "http://localhost:8001/gmail_oauth/callback")
    monkeypatch.setenv("GMAIL_REDIRECT_URI_PROD", "https://evolvianai.com/gmail_oauth/callback")
    monkeypatch.delenv("GMAIL_REDIRECT_URI", raising=False)

    request = _make_request("evolvianai.net")
    resolved = _resolve_gmail_redirect_uri(request)

    assert resolved == "https://evolvianai.net/gmail_oauth/callback"


def test_gmail_redirect_uri_ignores_mismatched_legacy_env(monkeypatch):
    monkeypatch.setenv("GMAIL_REDIRECT_URI", "https://evolvianai.net/gmail_oauth/callback2")
    monkeypatch.setenv("GMAIL_REDIRECT_URI_PROD", "https://evolvianai.com/gmail_oauth/callback")
    monkeypatch.delenv("GMAIL_REDIRECT_URI_LOCAL", raising=False)

    request = _make_request("evolvianai.com")
    resolved = _resolve_gmail_redirect_uri(request)

    assert resolved == "https://evolvianai.com/gmail_oauth/callback"

