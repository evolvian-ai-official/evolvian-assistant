from types import SimpleNamespace

from starlette.requests import Request


class _FakeDocumentMetadataQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, _fields):
        return self

    def eq(self, _column, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeStorageBucket:
    def __init__(self, storage_rows, signed_payload=None, fail_sign=False):
        self._storage_rows = storage_rows
        self._signed_payload = signed_payload or {"signedURL": "https://signed.local/file"}
        self._fail_sign = fail_sign

    def list(self, path):
        assert isinstance(path, str)
        return self._storage_rows

    def create_signed_url(self, path, expires_in):
        assert isinstance(path, str)
        assert expires_in == 3600
        if self._fail_sign:
            raise RuntimeError("signing_failed")
        return self._signed_payload


class _FakeStorage:
    def __init__(self, bucket):
        self._bucket = bucket

    def from_(self, bucket_name):
        assert bucket_name == "evolvian-documents"
        return self._bucket


class _FakeSupabase:
    def __init__(self, metadata_rows, storage_rows, signed_payload=None, fail_sign=False):
        self._metadata_rows = metadata_rows
        self.storage = _FakeStorage(
            _FakeStorageBucket(
                storage_rows=storage_rows,
                signed_payload=signed_payload,
                fail_sign=fail_sign,
            )
        )

    def table(self, table_name: str):
        assert table_name == "document_metadata"
        return _FakeDocumentMetadataQuery(self._metadata_rows)


def _request() -> Request:
    scope = {"type": "http", "headers": []}
    return Request(scope)


def test_list_files_uses_metadata_and_deduplicates(monkeypatch):
    from api import list_files_api as module

    metadata_rows = [
        {
            "storage_path": "client-1/policies.pdf",
            "file_name": "policies.pdf",
            "indexed_at": "2026-02-19T20:00:00Z",
        },
        {
            "storage_path": "client-1/policies.pdf",  # duplicated active row
            "file_name": "policies.pdf",
            "indexed_at": "2026-02-19T20:00:01Z",
        },
        {
            "storage_path": "client-1/faq.txt",
            "file_name": "faq.txt",
            "indexed_at": "2026-02-19T20:00:02Z",
        },
    ]
    storage_rows = [
        {"name": "policies.pdf", "updated_at": "2026-02-19T20:10:00Z", "metadata": {"size": 2048}},
        {"name": "faq.txt", "updated_at": "2026-02-19T20:11:00Z", "metadata": {"size": 1024}},
    ]

    monkeypatch.setattr(module, "supabase", _FakeSupabase(metadata_rows, storage_rows))
    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)

    result = module.list_files(_request(), client_id="client-1")
    files = result["files"]

    assert len(files) == 2
    assert files[0]["name"] == "faq.txt"
    assert files[0]["size_kb"] == 1.0
    assert files[1]["name"] == "policies.pdf"
    assert files[1]["size_kb"] == 2.0
    assert files[1]["signed_url"] == "https://signed.local/file"


def test_list_files_keeps_items_when_signed_url_generation_fails(monkeypatch):
    from api import list_files_api as module

    metadata_rows = [
        {
            "storage_path": "client-2/manual.pdf",
            "file_name": "manual.pdf",
            "indexed_at": "2026-02-19T20:15:00Z",
        }
    ]
    storage_rows = [{"name": "manual.pdf", "updated_at": "2026-02-19T20:16:00Z", "metadata": {"size": 512}}]

    monkeypatch.setattr(
        module,
        "supabase",
        _FakeSupabase(metadata_rows, storage_rows, fail_sign=True),
    )
    monkeypatch.setattr(module, "authorize_client_request", lambda _request, _client_id: None)

    result = module.list_files(_request(), client_id="client-2")
    files = result["files"]

    assert len(files) == 1
    assert files[0]["name"] == "manual.pdf"
    assert files[0]["size_kb"] == 0.5
    assert files[0]["signed_url"] is None

