import os
import sys

sys.path.insert(0, os.getcwd())

from api.security.log_redaction import sanitize_for_logging


def test_sanitize_for_logging_redacts_waba_fields_in_dict():
    payload = {
        "wa_business_account_id": "123456789012345",
        "waba_id": "9876543210",
        "ok": "value",
    }

    safe = sanitize_for_logging(payload)
    assert safe["wa_business_account_id"] == "***redacted***"
    assert safe["waba_id"] == "***redacted***"
    assert safe["ok"] == "value"


def test_sanitize_for_logging_redacts_waba_field_in_text():
    raw = "setup failed waba_id=123456789012345 token=EAABBBCCCDDDEEEFFF111222333"
    safe = sanitize_for_logging(raw)
    assert "waba_id: ***redacted***" in safe
    assert "token: ***redacted***" in safe
    assert "123456789012345" not in safe
