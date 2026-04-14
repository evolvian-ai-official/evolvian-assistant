from types import SimpleNamespace
import zipfile


def _doc(char_count: int):
    return SimpleNamespace(page_content=("x" * char_count))


def test_load_pdf_with_fallback_rejects_pdf_over_page_limit(monkeypatch):
    from api.modules import document_processor

    monkeypatch.setattr(document_processor, "MAX_PDF_PAGES", 3)
    monkeypatch.setattr(
        document_processor,
        "PdfReader",
        lambda _path: SimpleNamespace(pages=[object(), object(), object(), object()]),
    )

    try:
        document_processor.load_pdf_with_fallback("/tmp/fake.pdf")
        assert False, "Expected DocumentTooLargeError"
    except document_processor.DocumentTooLargeError as error:
        assert "límite seguro de páginas" in str(error)


def test_enforce_document_limits_rejects_large_text(monkeypatch):
    from api.modules import document_processor

    monkeypatch.setattr(document_processor, "MAX_PDF_PAGES", 100)
    monkeypatch.setattr(document_processor, "MAX_DOCUMENT_CHARS", 10)

    try:
        document_processor._enforce_document_limits([_doc(6), _doc(6)])
        assert False, "Expected DocumentTooLargeError"
    except document_processor.DocumentTooLargeError as error:
        assert "límite seguro de texto extraído" in str(error)


def test_enforce_chunk_limit_rejects_large_chunk_count(monkeypatch):
    from api.modules import document_processor

    monkeypatch.setattr(document_processor, "MAX_DOCUMENT_CHUNKS", 2)

    try:
        document_processor._enforce_chunk_limit([object(), object(), object()])
        assert False, "Expected DocumentTooLargeError"
    except document_processor.DocumentTooLargeError as error:
        assert "demasiados chunks" in str(error)


def test_save_to_chroma_ingests_in_batches(monkeypatch):
    from api.modules import chroma_indexer

    calls = []

    class _FakeVectorStore:
        def add_documents(self, batch):
            calls.append([doc.page_content for doc in batch])

        def persist(self):
            calls.append("persist")

    monkeypatch.setattr(chroma_indexer, "CHROMA_INGEST_BATCH_SIZE", 2)
    monkeypatch.setattr(
        chroma_indexer,
        "get_chroma_vectorstore",
        lambda client_id=None, persist=True: _FakeVectorStore(),
    )

    docs = [_doc(1), _doc(2), _doc(3), _doc(4), _doc(5)]
    chroma_indexer.save_to_chroma(docs, "client-1")

    assert calls == [
        ["x", "xx"],
        ["xxx", "xxxx"],
        ["xxxxx"],
        "persist",
    ]


def test_load_docx_with_fallback_extracts_text(tmp_path):
    from api.modules import document_processor

    docx_path = tmp_path / "sample.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>"
                "<w:p><w:r><w:t>Hola</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Mundo</w:t></w:r></w:p>"
                "</w:body>"
                "</w:document>"
            ),
        )

    docs = document_processor.load_docx_with_fallback(str(docx_path))

    assert len(docs) == 1
    assert docs[0].page_content == "Hola\nMundo"


def test_validate_upload_candidate_blocks_images_and_large_pdfs():
    from fastapi import HTTPException
    from api import upload_document

    try:
        upload_document._validate_upload_candidate("hero.png", "image/png", 100)
        assert False, "Expected HTTPException"
    except HTTPException as error:
        assert error.detail == "image_uploads_not_allowed"

    try:
        upload_document._validate_upload_candidate(
            "manual.pdf",
            "application/pdf",
            upload_document.PDF_MAX_FILE_SIZE_BYTES + 1,
        )
        assert False, "Expected HTTPException"
    except HTTPException as error:
        assert error.detail == "pdf_file_too_large"


def test_validate_upload_candidate_allows_docx():
    from api import upload_document

    upload_document._validate_upload_candidate(
        "playbook.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        1024,
    )
