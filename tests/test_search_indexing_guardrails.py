from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_sensitive_html_entrypoints_include_noindex_meta():
    html_paths = [
        "front_end/clientuploader/index.html",
        "front_end/clientuploader/public/chat-widget.html",
        "static/index.html",
        "static/widget.html",
        "static/chat-widget.html",
    ]

    for relative_path in html_paths:
        content = _read(relative_path)
        assert 'name="robots" content="noindex,nofollow,noarchive,nosnippet"' in content
        assert 'name="googlebot" content="noindex,nofollow,noarchive,nosnippet"' in content


def test_public_examples_do_not_ship_real_client_ids():
    public_example_paths = [
        "static/test.html",
        "static/examples/test_iframe.html",
        "static/examples/clinica.html",
        "front_end/clientuploader/public/test.html",
        "front_end/clientuploader/public/examples/test_iframe.html",
        "front_end/clientuploader/public/examples/clinica.html",
    ]

    forbidden_ids = [
        "ug86ef4xpykf",
        "5x0q6xsu7wf7",
    ]

    for relative_path in public_example_paths:
        content = _read(relative_path)
        assert "YOUR_PUBLIC_CLIENT_ID" in content
        for forbidden_id in forbidden_ids:
            assert forbidden_id not in content
