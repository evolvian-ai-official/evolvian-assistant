import importlib


def _load_module():
    return importlib.import_module("api.modules.assistant_rag.rag_pipeline")


def test_guess_language_detects_spanish_with_typo_and_odd_accent():
    module = _load_module()
    text = "tieens informacio´n de la veterinaria?"
    assert module._guess_lang_es_en(text) == "es"


def test_guess_language_detects_english_question():
    module = _load_module()
    text = "Do you have information about the veterinary services?"
    assert module._guess_lang_es_en(text) == "en"


def test_resolve_language_falls_back_to_client_language_when_ambiguous(monkeypatch):
    module = _load_module()

    monkeypatch.setattr(module, "_guess_lang_es_en", lambda _text: None)
    monkeypatch.setattr(module, "_safe_langdetect", lambda _text: None)
    monkeypatch.setattr(module, "_client_language_fallback", lambda _client_id: "es")

    resolved = module._resolve_user_language("client_1", "asdf qwer zxcv")
    assert resolved == "es"


def test_resolve_language_prefers_detected_spanish_over_client_english(monkeypatch):
    module = _load_module()

    monkeypatch.setattr(module, "_client_language_fallback", lambda _client_id: "en")
    resolved = module._resolve_user_language("client_1", "Tienes información de la veterinaria?")
    assert resolved == "es"

