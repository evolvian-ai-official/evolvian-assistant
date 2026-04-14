from types import SimpleNamespace


class _FakeTable:
    def __init__(self, table_name: str, state: dict):
        self._table_name = table_name
        self._state = state
        self._filters = []
        self._op = None
        self._payload = None

    def select(self, _query):
        self._op = "select"
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def execute(self):
        rows = self._state.setdefault(self._table_name, [])
        matched = [
            row for row in rows
            if all(row.get(field) == value for field, value in self._filters)
        ]

        if self._op == "select":
            return SimpleNamespace(data=[dict(row) for row in matched])

        if self._op == "update":
            updated = []
            for row in rows:
                if all(row.get(field) == value for field, value in self._filters):
                    row.update(self._payload)
                    updated.append(dict(row))
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=[])


class _FakeSupabase:
    def __init__(self, state: dict):
        self._state = state

    def table(self, table_name: str):
        return _FakeTable(table_name, self._state)


def test_reindex_client_returns_partial_failure_and_marks_successful_docs(monkeypatch, tmp_path):
    from api.internal import reindex_single_client

    state = {
        "document_metadata": [
            {"client_id": "client-1", "storage_path": "client-1/a.pdf", "is_active": True},
            {"client_id": "client-1", "storage_path": "client-1/b.pdf", "is_active": True},
        ]
    }
    fake_supabase = _FakeSupabase(state)
    monkeypatch.setattr(reindex_single_client, "supabase", fake_supabase)
    monkeypatch.setattr(reindex_single_client, "get_base_data_path", lambda: str(tmp_path))
    monkeypatch.setattr(reindex_single_client, "get_signed_url", lambda storage_path: f"https://signed/{storage_path}")

    def _fake_process_file(
        file_url: str,
        client_id: str,
        storage_path: str | None = None,
        return_chunks: bool = True,
    ):
        if storage_path == "client-1/b.pdf":
            raise RuntimeError("broken document")
        if return_chunks:
            return [{"file_url": file_url, "client_id": client_id, "storage_path": storage_path}]
        return None

    monkeypatch.setattr(reindex_single_client, "process_file", _fake_process_file)

    chroma_path = tmp_path / "chroma_client-1"
    chroma_path.mkdir()
    (chroma_path / "old.sqlite3").write_text("stale-index", encoding="utf-8")

    result = reindex_single_client.reindex_client("client-1")

    assert result["status"] == "partial_failure"
    assert result["docs_total"] == 2
    assert result["docs_reindexed"] == 1
    assert result["docs_failed"] == 1
    assert result["failed_paths"] == ["client-1/b.pdf"]
    assert str(chroma_path) in result["cleared_paths"]

    metadata_rows = state["document_metadata"]
    indexed_a = next(row for row in metadata_rows if row["storage_path"] == "client-1/a.pdf")
    indexed_b = next(row for row in metadata_rows if row["storage_path"] == "client-1/b.pdf")
    assert "indexed_at" in indexed_a
    assert "indexed_at" not in indexed_b


def test_reindex_all_clients_reports_failed_clients(monkeypatch):
    from api.internal import reindex_all_clients

    state = {
        "document_metadata": [
            {"client_id": "client-1", "is_active": True},
            {"client_id": "client-2", "is_active": True},
            {"client_id": "client-2", "is_active": True},
        ]
    }
    monkeypatch.setattr(reindex_all_clients, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(
        reindex_all_clients,
        "reindex_client",
        lambda client_id: {
            "client_id": client_id,
            "status": "partial_failure" if client_id == "client-2" else "success",
        },
    )

    result = reindex_all_clients.reindex_all_clients()

    assert result["clients_total"] == 2
    assert result["clients_ok"] == 1
    assert result["clients_with_failures"] == 1
    assert [row["client_id"] for row in result["failed_clients"]] == ["client-2"]


def test_audit_document_index_health_flags_missing_indexes_and_indexed_at(monkeypatch, tmp_path):
    from api.internal import audit_document_index_health

    state = {
        "document_metadata": [
            {
                "client_id": "client-1",
                "storage_path": "client-1/a.pdf",
                "indexed_at": "2026-04-14T12:00:00Z",
                "is_active": True,
            },
            {
                "client_id": "client-2",
                "storage_path": "client-2/b.pdf",
                "indexed_at": "",
                "is_active": True,
            },
            {
                "client_id": "client-3",
                "storage_path": "client-3/c.pdf",
                "indexed_at": "2026-04-14T12:05:00Z",
                "is_active": True,
            },
        ]
    }
    monkeypatch.setattr(audit_document_index_health, "supabase", _FakeSupabase(state))
    monkeypatch.setattr(audit_document_index_health, "get_base_data_path", lambda: str(tmp_path))

    chroma_client_1 = tmp_path / "chroma_client-1"
    chroma_client_1.mkdir()
    (chroma_client_1 / "index.bin").write_text("ok", encoding="utf-8")

    chroma_client_3 = tmp_path / "chroma_client-3"
    chroma_client_3.mkdir()

    result = audit_document_index_health.audit_document_index_health()

    assert result["clients_total"] == 3
    assert result["clients_at_risk"] == 2

    risk_by_client = {row["client_id"]: row for row in result["at_risk_clients"]}
    assert risk_by_client["client-2"]["risk_reasons"] == [
        "missing_or_empty_chroma_index",
        "missing_indexed_at",
    ]
    assert risk_by_client["client-3"]["risk_reasons"] == ["missing_or_empty_chroma_index"]
