from starlette.requests import Request

from api.auth.google_calendar_callback import _resolve_token_exchange_redirect_uri


def _make_request(host: str, scheme: str = "https") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/auth/google_calendar/callback",
        "raw_path": b"/api/auth/google_calendar/callback",
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


def test_resolve_token_exchange_redirect_uri_prefers_signed_state_uri_when_allowed(monkeypatch):
    monkeypatch.setenv("GOOGLE_REDIRECT_URI_LOCAL", "http://localhost:8001/api/auth/google_calendar/callback")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI_PROD", "https://evolvianai.com/api/auth/google_calendar/callback")
    request = _make_request("evolvianai.net")

    state_payload = {
        "oauth_redirect_uri": "https://evolvianai.net/api/auth/google_calendar/callback",
    }

    resolved = _resolve_token_exchange_redirect_uri(request, state_payload)
    assert resolved == "https://evolvianai.net/api/auth/google_calendar/callback"


def test_resolve_token_exchange_redirect_uri_falls_back_when_state_uri_not_allowed(monkeypatch):
    monkeypatch.setenv("GOOGLE_REDIRECT_URI_LOCAL", "http://localhost:8001/api/auth/google_calendar/callback")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI_PROD", "https://evolvianai.com/api/auth/google_calendar/callback")
    request = _make_request("evolvianai.com")

    state_payload = {
        "oauth_redirect_uri": "https://evil.example.com/api/auth/google_calendar/callback",
    }

    resolved = _resolve_token_exchange_redirect_uri(request, state_payload)
    assert resolved == "https://evolvianai.com/api/auth/google_calendar/callback"

