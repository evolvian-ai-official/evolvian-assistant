import hashlib
import hmac
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from api.webhook_security import _is_enabled, verify_meta_signature


def _build_request(headers=None):
    headers = headers or {}
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/webhook",
        "query_string": b"",
        "headers": [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


class IsEnabledTests(unittest.TestCase):
    def test_is_enabled_defaults_to_true_when_missing(self):
        self.assertTrue(_is_enabled(None))

    def test_is_enabled_recognizes_false_values(self):
        self.assertFalse(_is_enabled("false"))
        self.assertFalse(_is_enabled("0"))
        self.assertFalse(_is_enabled("off"))

    def test_is_enabled_recognizes_true_values(self):
        self.assertTrue(_is_enabled("true"))
        self.assertTrue(_is_enabled("1"))
        self.assertTrue(_is_enabled("yes"))


class VerifyMetaSignatureTests(unittest.TestCase):
    def setUp(self):
        self.body = b'{"event":"ping"}'
        self.secret = "top-secret"

    def test_skip_when_signature_validation_disabled(self):
        request = _build_request()
        with patch.dict(os.environ, {"META_VERIFY_SIGNATURE": "false", "META_APP_SECRET": self.secret}, clear=False):
            verify_meta_signature(request, self.body)

    def test_skip_when_secret_missing(self):
        request = _build_request()
        with patch.dict(os.environ, {"META_VERIFY_SIGNATURE": "true"}, clear=False):
            os.environ.pop("META_APP_SECRET", None)
            verify_meta_signature(request, self.body)

    def test_raises_when_header_missing(self):
        request = _build_request()
        with patch.dict(os.environ, {"META_VERIFY_SIGNATURE": "true", "META_APP_SECRET": self.secret}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                verify_meta_signature(request, self.body)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail, "missing_meta_signature")

    def test_raises_when_signature_invalid(self):
        request = _build_request({"X-Hub-Signature-256": "sha256=invalid"})
        with patch.dict(os.environ, {"META_VERIFY_SIGNATURE": "true", "META_APP_SECRET": self.secret}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                verify_meta_signature(request, self.body)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail, "invalid_meta_signature")

    def test_accepts_valid_signature(self):
        valid_sig = hmac.new(self.secret.encode("utf-8"), self.body, hashlib.sha256).hexdigest()
        request = _build_request({"X-Hub-Signature-256": f"sha256={valid_sig}"})
        with patch.dict(os.environ, {"META_VERIFY_SIGNATURE": "true", "META_APP_SECRET": self.secret}, clear=False):
            verify_meta_signature(request, self.body)


if __name__ == "__main__":
    unittest.main()
