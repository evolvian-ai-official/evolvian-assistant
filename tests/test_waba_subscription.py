import os
import sys

sys.path.insert(0, os.getcwd())

from api.modules.whatsapp import template_sync as module


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


def test_ensure_waba_app_subscription_success(monkeypatch):
    def _fake_meta_request(*_args, **_kwargs):
        return _FakeResponse(200, {"success": True})

    monkeypatch.setattr(module, "_meta_request", _fake_meta_request)

    result = module.ensure_waba_app_subscription(waba_id="123456789", wa_token="EAABC1234567890TOKEN")
    assert result["success"] is True
    assert result["already_subscribed"] is False


def test_ensure_waba_app_subscription_already_subscribed(monkeypatch):
    def _fake_meta_request(*_args, **_kwargs):
        return _FakeResponse(
            400,
            {
                "error": {
                    "message": "App is already subscribed to this WhatsApp Business Account.",
                    "code": 100,
                }
            },
        )

    monkeypatch.setattr(module, "_meta_request", _fake_meta_request)

    result = module.ensure_waba_app_subscription(waba_id="123456789", wa_token="EAABC1234567890TOKEN")
    assert result["success"] is True
    assert result["already_subscribed"] is True


def test_ensure_waba_app_subscription_propagates_meta_error(monkeypatch):
    def _fake_meta_request(*_args, **_kwargs):
        return _FakeResponse(
            403,
            {
                "error": {
                    "message": "(#200) Permissions error",
                    "code": 200,
                    "error_subcode": 33,
                }
            },
        )

    monkeypatch.setattr(module, "_meta_request", _fake_meta_request)

    result = module.ensure_waba_app_subscription(waba_id="123456789", wa_token="EAABC1234567890TOKEN")
    assert result["success"] is False
    assert result["already_subscribed"] is False
    assert result["status_code"] == 403
    assert "Permissions error" in result["error"]


def test_ensure_waba_app_subscription_requires_waba_and_token():
    result = module.ensure_waba_app_subscription(waba_id="", wa_token="")
    assert result["success"] is False
    assert result["error"] == "missing_waba_id_or_token"


def test_get_waba_subscription_status_success(monkeypatch):
    def _fake_meta_request(*_args, **_kwargs):
        return _FakeResponse(
            200,
            {
                "data": [
                    {"id": "123", "name": "App 1"},
                    {"id": "456", "name": "App 2"},
                ]
            },
        )

    monkeypatch.setattr(module, "_meta_request", _fake_meta_request)
    result = module.get_waba_subscription_status(waba_id="123456789", wa_token="EAABC1234567890TOKEN")
    assert result["success"] is True
    assert result["subscribed"] is True
    assert result["app_count"] == 2


def test_fetch_phone_number_metadata_fallback_on_unknown_field(monkeypatch):
    responses = [
        _FakeResponse(
            400,
            {
                "error": {
                    "message": "Tried accessing nonexisting field (status) on node type (WhatsAppBusinessPhoneNumber)",
                    "code": 100,
                }
            },
        ),
        _FakeResponse(
            200,
            {
                "id": "999",
                "display_phone_number": "+52 55 1234 5678",
                "code_verification_status": "VERIFIED",
                "quality_rating": "GREEN",
            },
        ),
    ]

    def _fake_meta_request(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(module, "_meta_request", _fake_meta_request)
    result = module.fetch_phone_number_metadata(wa_phone_id="999", wa_token="EAABC1234567890TOKEN")
    assert result["success"] is True
    assert result["data"]["display_phone_number"] == "+52 55 1234 5678"
    assert result["data"]["code_verification_status"] == "VERIFIED"


def test_is_phone_number_approved_detects_verified_status():
    approved = module.is_phone_number_approved(
        phone_metadata={
            "code_verification_status": "verified",
            "name_status": "pending",
            "status": "active",
        }
    )
    assert approved is True

    not_approved = module.is_phone_number_approved(
        phone_metadata={
            "code_verification_status": "pending",
            "name_status": "requested",
            "status": "unknown",
        }
    )
    assert not_approved is False
