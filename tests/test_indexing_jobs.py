from types import SimpleNamespace


class _FakeTable:
    def __init__(self, table_name: str, rows: dict[str, list[dict]]):
        self._table_name = table_name
        self._rows = rows
        self._filters = []

    def select(self, _query):
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def execute(self):
        table_rows = self._rows.get(self._table_name, [])
        filtered = [
            row for row in table_rows
            if all(row.get(field) == value for field, value in self._filters)
        ]
        return SimpleNamespace(data=filtered)


class _FakeSupabase:
    def __init__(self, rows: dict[str, list[dict]]):
        self._rows = rows

    def table(self, table_name: str):
        return _FakeTable(table_name, self._rows)


def test_select_target_client_ids_prefers_at_risk_clients(monkeypatch):
    from api.internal import indexing_jobs

    monkeypatch.setattr(
        indexing_jobs,
        "audit_document_index_health",
        lambda: {
            "at_risk_clients": [
                {"client_id": "client-b"},
                {"client_id": "client-c"},
            ]
        },
    )

    payload = indexing_jobs.ReindexBatchPayload(max_clients=1, only_at_risk=True)
    target_ids = indexing_jobs._select_target_client_ids(payload)

    assert target_ids == ["client-b"]


def test_reindex_stale_clients_returns_locked_status(monkeypatch):
    from fastapi import HTTPException
    from api.internal import indexing_jobs

    monkeypatch.setattr(indexing_jobs, "require_internal_request", lambda _request: None)
    monkeypatch.setattr(
        indexing_jobs,
        "_select_target_client_ids",
        lambda _payload: ["client-1"],
    )
    monkeypatch.setattr(
        indexing_jobs,
        "_runtime_context",
        lambda: {"base_data_path": "/tmp/evolvian"},
    )

    class _LockedContext:
        def __enter__(self):
            raise HTTPException(status_code=409, detail="reindex_batch_already_running")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(indexing_jobs, "_reindex_lock", lambda: _LockedContext())

    result = indexing_jobs.reindex_stale_clients(
        indexing_jobs.ReindexBatchPayload(),
        request=SimpleNamespace(),
    )

    assert result["status"] == "locked"
    assert result["selected_client_ids"] == ["client-1"]


def test_reindex_stale_clients_reindexes_selected_batch(monkeypatch):
    from api.internal import indexing_jobs

    monkeypatch.setattr(indexing_jobs, "require_internal_request", lambda _request: None)
    monkeypatch.setattr(
        indexing_jobs,
        "supabase",
        _FakeSupabase(
            {
                "document_metadata": [
                    {"client_id": "client-2", "is_active": True},
                    {"client_id": "client-1", "is_active": True},
                    {"client_id": "client-1", "is_active": True},
                ]
            }
        ),
    )
    monkeypatch.setattr(
        indexing_jobs,
        "audit_document_index_health",
        lambda: {"at_risk_clients": []},
    )
    monkeypatch.setattr(
        indexing_jobs,
        "_runtime_context",
        lambda: {"base_data_path": "/tmp/evolvian"},
    )

    calls = []
    monkeypatch.setattr(
        indexing_jobs,
        "reindex_client",
        lambda client_id: calls.append(client_id) or {"client_id": client_id, "status": "success"},
    )

    class _UnlockedContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(indexing_jobs, "_reindex_lock", lambda: _UnlockedContext())

    result = indexing_jobs.reindex_stale_clients(
        indexing_jobs.ReindexBatchPayload(max_clients=2, only_at_risk=False),
        request=SimpleNamespace(),
    )

    assert result["status"] == "success"
    assert result["selected_client_ids"] == ["client-1", "client-2"]
    assert calls == ["client-1", "client-2"]
