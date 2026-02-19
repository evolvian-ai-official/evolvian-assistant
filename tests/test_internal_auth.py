import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.internal_auth import (
    has_valid_internal_token,
    require_internal_request,
)


def _request_with_headers(headers: dict[str, str] | None = None) -> Request:
    raw = []
    for key, value in (headers or {}).items():
        raw.append((key.lower().encode("utf-8"), value.encode("utf-8")))
    scope = {"type": "http", "headers": raw}
    return Request(scope)


def test_has_valid_internal_token(monkeypatch):
    monkeypatch.setenv("EVOLVIAN_INTERNAL_TASK_TOKEN", "top-secret")
    request = _request_with_headers({"x-evolvian-internal-token": "top-secret"})
    assert has_valid_internal_token(request) is True


def test_require_internal_request_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("EVOLVIAN_INTERNAL_TASK_TOKEN", "top-secret")
    request = _request_with_headers()
    with pytest.raises(HTTPException) as exc:
        require_internal_request(request)
    assert exc.value.detail == "invalid_internal_task_token"
