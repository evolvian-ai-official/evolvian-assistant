from urllib.parse import parse_qs, urlparse

from api.marketing_campaigns import _build_unsubscribe_url
from api.security import unsubscribe_client_id_crypto as crypto


def test_build_unsubscribe_url_encrypts_client_id(monkeypatch):
    monkeypatch.setenv("UNSUBSCRIBE_LINK_ENCRYPTION_KEY", "unit-test-unsubscribe-secret")
    monkeypatch.setenv("EVOLVIAN_API_BASE_URL", "https://example.evolvian.test")
    crypto._get_fernet_optional.cache_clear()

    raw_client_id = "ce09c2dc-fa5f-48d7-82b7-95a09213c2d9"
    url = _build_unsubscribe_url(
        base_url=None,
        email="aldo.benitez.cortes@gmail.com",
        client_id=raw_client_id,
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    encrypted_client_id = query["client_id"][0]

    assert query["email"][0] == "aldo.benitez.cortes@gmail.com"
    assert encrypted_client_id != raw_client_id
    assert encrypted_client_id.startswith("cid:v1:")
    assert crypto.decrypt_unsubscribe_client_id(encrypted_client_id) == raw_client_id
