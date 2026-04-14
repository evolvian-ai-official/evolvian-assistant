from datetime import datetime, timezone
from types import SimpleNamespace

from api import terms_api


class _FakeTable:
    def __init__(self, table_name: str, *, terms_rows: list[dict], profile_row: dict | None):
        self._table_name = table_name
        self._terms_rows = terms_rows
        self._profile_row = profile_row
        self._maybe_single = False

    def select(self, _query):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def execute(self):
        if self._table_name == "client_terms_acceptance":
            return SimpleNamespace(data=self._terms_rows)
        if self._table_name == "client_profile":
            if self._maybe_single:
                return SimpleNamespace(data=self._profile_row)
            return SimpleNamespace(data=[self._profile_row] if self._profile_row else [])
        raise AssertionError(f"Unexpected table {self._table_name}")


class _FakeSupabase:
    def __init__(self, *, terms_rows: list[dict], profile_row: dict | None):
        self._terms_rows = terms_rows
        self._profile_row = profile_row

    def table(self, table_name: str):
        return _FakeTable(
            table_name,
            terms_rows=self._terms_rows,
            profile_row=self._profile_row,
        )


def test_terms_valid_days_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("TERMS_ACCEPTANCE_VALID_DAYS", raising=False)
    assert terms_api._terms_valid_days() == 0


def test_terms_valid_days_parses_positive_int(monkeypatch):
    monkeypatch.setenv("TERMS_ACCEPTANCE_VALID_DAYS", "45")
    assert terms_api._terms_valid_days() == 45


def test_terms_valid_days_rejects_invalid(monkeypatch):
    monkeypatch.setenv("TERMS_ACCEPTANCE_VALID_DAYS", "abc")
    assert terms_api._terms_valid_days() == 0


def test_parse_accepted_at_handles_iso_with_z():
    parsed = terms_api._parse_accepted_at("2026-02-19T13:00:00Z")
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo == timezone.utc


def test_parse_accepted_at_returns_none_for_bad_value():
    assert terms_api._parse_accepted_at("not-a-date") is None


def test_should_show_welcome_when_required_profile_fields_are_missing(monkeypatch):
    monkeypatch.delenv("TERMS_ACCEPTANCE_VALID_DAYS", raising=False)
    monkeypatch.setattr(
        terms_api,
        "supabase",
        _FakeSupabase(
            terms_rows=[
                {
                    "accepted": True,
                    "accepted_at": "2026-04-14T10:00:00Z",
                    "version": "v1",
                }
            ],
            profile_row={"industry": "Healthcare", "discovery_source": " "},
        ),
    )
    monkeypatch.setattr(terms_api, "authorize_client_request", lambda _request, _client_id: None)

    response = terms_api.should_show_welcome(SimpleNamespace(), client_id="client-1")

    assert response["show"] is True
    assert response["reason"] == "missing_profile_fields"
    assert response["missing_fields"] == ["discovery_source"]


def test_should_not_show_welcome_when_terms_are_valid_and_profile_is_complete(monkeypatch):
    monkeypatch.delenv("TERMS_ACCEPTANCE_VALID_DAYS", raising=False)
    monkeypatch.setattr(
        terms_api,
        "supabase",
        _FakeSupabase(
            terms_rows=[
                {
                    "accepted": True,
                    "accepted_at": "2026-04-14T10:00:00Z",
                    "version": "v1",
                }
            ],
            profile_row={
                "industry": "Healthcare",
                "discovery_source": "Instagram",
            },
        ),
    )
    monkeypatch.setattr(terms_api, "authorize_client_request", lambda _request, _client_id: None)

    response = terms_api.should_show_welcome(SimpleNamespace(), client_id="client-1")

    assert response["show"] is False
    assert response["reason"] == "accepted_no_expiry"
