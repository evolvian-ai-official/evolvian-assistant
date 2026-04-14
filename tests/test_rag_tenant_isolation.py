import importlib
from types import SimpleNamespace


def _load_module():
    return importlib.import_module("api.modules.assistant_rag.rag_pipeline")


def _doc(text: str, metadata):
    return SimpleNamespace(page_content=text, metadata=metadata)


def test_filter_retrieved_docs_keeps_only_active_docs_for_current_client():
    module = _load_module()

    retrieved_docs = [
        _doc(
            "client 1 valid",
            {"client_id": "client-1", "storage_path": "client-1/faq.pdf"},
        ),
        _doc(
            "client 2 leaked",
            {"client_id": "client-2", "storage_path": "client-2/faq.pdf"},
        ),
        _doc(
            "inactive same client",
            {"client_id": "client-1", "storage_path": "client-1/old.pdf"},
        ),
        _doc("missing metadata", None),
    ]

    filtered_docs = module._filter_retrieved_docs_for_client(
        retrieved_docs,
        client_id="client-1",
        active_storage_paths={"client-1/faq.pdf"},
    )

    assert len(filtered_docs) == 1
    assert filtered_docs[0].page_content == "client 1 valid"


def test_filter_retrieved_docs_allows_legacy_chunks_when_storage_path_matches_client():
    module = _load_module()

    retrieved_docs = [
        _doc("legacy same client", {"storage_path": "client-1/manual.txt"}),
        _doc("legacy other client", {"storage_path": "client-2/manual.txt"}),
    ]

    filtered_docs = module._filter_retrieved_docs_for_client(
        retrieved_docs,
        client_id="client-1",
        active_storage_paths={"client-1/manual.txt"},
    )

    assert len(filtered_docs) == 1
    assert filtered_docs[0].page_content == "legacy same client"


def test_ask_question_falls_back_when_retrieval_only_returns_foreign_docs(monkeypatch, tmp_path):
    module = _load_module()

    class _FakeRetriever:
        def __init__(self, docs):
            self._docs = docs

        def invoke(self, _question):
            return self._docs

    class _FakeChroma:
        def __init__(self, **_kwargs):
            pass

        def as_retriever(self, **_kwargs):
            return _FakeRetriever(
                [
                    _doc(
                        "foreign content",
                        {"client_id": "client-2", "storage_path": "client-2/secret.pdf"},
                    )
                ]
            )

    client_dir = tmp_path / "chroma_client-1"
    client_dir.mkdir()

    monkeypatch.setattr(module, "get_prompt_for_client", lambda _client_id: "")
    monkeypatch.setattr(module, "get_temperature_for_client", lambda _client_id: 0.2)
    monkeypatch.setattr(module, "get_language_for_client", lambda _client_id: "es")
    monkeypatch.setattr(module, "_resolve_user_language", lambda _client_id, _text: "es")
    monkeypatch.setattr(module, "_has_active_documents", lambda _client_id: True)
    monkeypatch.setattr(module, "get_base_data_path", lambda: str(tmp_path))
    monkeypatch.setattr(module, "_rewrite_for_retrieval", lambda _memory, question: question)
    monkeypatch.setattr(module, "_get_active_storage_paths", lambda _client_id: {"client-1/faq.pdf"})
    monkeypatch.setattr(module, "save_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "OpenAIEmbeddings", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "Chroma", _FakeChroma)

    result = module.ask_question(
        messages="Que informacion tienes?",
        client_id="client-1",
        session_id="session-1",
        return_metadata=True,
        persist_history=False,
    )

    assert result["handoff_recommended"] is True
    assert result["handoff_reason"] == "no_retrieval_match"
    assert result["confidence_reason"] == "retriever_returned_no_docs"
    assert result["answer"] == module.FALLBACK_BY_LANG["es"]
