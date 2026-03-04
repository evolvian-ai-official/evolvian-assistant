from api.security import unsubscribe_client_id_crypto as crypto


def _clear_cipher_cache() -> None:
    crypto._get_fernet_optional.cache_clear()


def test_unsubscribe_client_id_crypto_roundtrip(monkeypatch):
    monkeypatch.setenv("UNSUBSCRIBE_LINK_ENCRYPTION_KEY", "unit-test-unsubscribe-secret")
    _clear_cipher_cache()

    raw_client_id = "ce09c2dc-fa5f-48d7-82b7-95a09213c2d9"
    encrypted = crypto.encrypt_unsubscribe_client_id(raw_client_id)

    assert encrypted.startswith("cid:v1:")
    assert raw_client_id not in encrypted
    assert crypto.decrypt_unsubscribe_client_id(encrypted) == raw_client_id


def test_unsubscribe_client_id_crypto_rejects_tampered_token(monkeypatch):
    monkeypatch.setenv("UNSUBSCRIBE_LINK_ENCRYPTION_KEY", "unit-test-unsubscribe-secret")
    _clear_cipher_cache()

    encrypted = crypto.encrypt_unsubscribe_client_id("client-123")
    replacement = "A" if encrypted[-1] != "A" else "B"
    tampered = f"{encrypted[:-1]}{replacement}"

    assert crypto.decrypt_unsubscribe_client_id(tampered) is None


def test_unsubscribe_client_id_crypto_supports_legacy_plaintext():
    assert crypto.decrypt_unsubscribe_client_id("legacy-client-id") == "legacy-client-id"
