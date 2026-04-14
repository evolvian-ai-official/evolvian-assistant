from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
import os


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

    monkeypatch.setattr(indexing_jobs, "_filter_retryable_client_ids", lambda ids: (ids, []))
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
        "_select_target_client_ids_with_context",
        lambda _payload: {
            "selected_client_ids": ["client-1"],
            "skipped_due_to_recent_failures": [],
        },
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

    monkeypatch.setattr(indexing_jobs, "_reindex_lock", lambda **_kwargs: _LockedContext())

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
    monkeypatch.setattr(indexing_jobs, "_filter_retryable_client_ids", lambda ids: (ids, []))
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

    monkeypatch.setattr(indexing_jobs, "_reindex_lock", lambda **_kwargs: _UnlockedContext())

    result = indexing_jobs.reindex_stale_clients(
        indexing_jobs.ReindexBatchPayload(max_clients=2, only_at_risk=False),
        request=SimpleNamespace(),
    )

    assert result["status"] == "success"
    assert result["selected_client_ids"] == ["client-1", "client-2"]
    assert calls == ["client-1", "client-2"]


def test_select_target_client_ids_skips_recent_failures(monkeypatch):
    from api.internal import indexing_jobs

    monkeypatch.setattr(
        indexing_jobs,
        "audit_document_index_health",
        lambda: {
            "at_risk_clients": [
                {"client_id": "client-a"},
                {"client_id": "client-b"},
                {"client_id": "client-c"},
            ]
        },
    )
    monkeypatch.setattr(
        indexing_jobs,
        "_filter_retryable_client_ids",
        lambda ids: ([client_id for client_id in ids if client_id != "client-a"], ["client-a"]),
    )

    result = indexing_jobs._select_target_client_ids_with_context(
        indexing_jobs.ReindexBatchPayload(max_clients=2, only_at_risk=True)
    )

    assert result["selected_client_ids"] == ["client-b", "client-c"]
    assert result["skipped_due_to_recent_failures"] == ["client-a"]


def test_reindex_stale_clients_reports_cooldown_when_only_failed_clients_are_skipped(monkeypatch):
    from api.internal import indexing_jobs

    monkeypatch.setattr(indexing_jobs, "require_internal_request", lambda _request: None)
    monkeypatch.setattr(
        indexing_jobs,
        "_select_target_client_ids_with_context",
        lambda _payload: {
            "selected_client_ids": [],
            "skipped_due_to_recent_failures": ["client-stuck"],
        },
    )
    monkeypatch.setattr(
        indexing_jobs,
        "_runtime_context",
        lambda: {"base_data_path": "/tmp/evolvian"},
    )

    result = indexing_jobs.reindex_stale_clients(
        indexing_jobs.ReindexBatchPayload(),
        request=SimpleNamespace(),
    )

    assert result["status"] == "cooldown"
    assert result["selected_client_ids"] == []
    assert result["skipped_due_to_recent_failures"] == ["client-stuck"]


def test_reindex_lock_reclaims_stale_lock(monkeypatch, tmp_path):
    from api.internal import indexing_jobs

    stale_lock_path = tmp_path / ".reindex-batch.lock"
    stale_lock_path.write_text(
        (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
        encoding="utf-8",
    )

    monkeypatch.setattr(indexing_jobs, "get_base_data_path", lambda: str(tmp_path))
    monkeypatch.setattr(indexing_jobs, "LOCK_STALE_AFTER_MINUTES", 15)

    with indexing_jobs._reindex_lock(selected_client_ids=["client-1"]):
        state = indexing_jobs._load_lock_state()
        assert state is not None
        assert state["selected_client_ids"] == ["client-1"]
        assert state["format"] == "json"

    assert not stale_lock_path.exists()


def test_reindex_lock_treats_old_empty_lock_as_stale(monkeypatch, tmp_path):
    from api.internal import indexing_jobs

    stale_lock_path = tmp_path / ".reindex-batch.lock"
    stale_lock_path.write_text("", encoding="utf-8")
    old_timestamp = datetime.now(timezone.utc) - timedelta(minutes=25)
    os.utime(stale_lock_path, (old_timestamp.timestamp(), old_timestamp.timestamp()))

    monkeypatch.setattr(indexing_jobs, "get_base_data_path", lambda: str(tmp_path))
    monkeypatch.setattr(indexing_jobs, "LOCK_STALE_AFTER_MINUTES", 15)

    with indexing_jobs._reindex_lock(selected_client_ids=["client-2"]):
        state = indexing_jobs._load_lock_state()
        assert state is not None
        assert state["selected_client_ids"] == ["client-2"]

    assert not stale_lock_path.exists()
