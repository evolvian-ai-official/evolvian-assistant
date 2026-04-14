from api.utils import paths


def test_get_base_data_path_prefers_explicit_override(monkeypatch, tmp_path):
    override_path = tmp_path / "custom-data"

    monkeypatch.setenv("EVOLVIAN_DATA_PATH", str(override_path))
    monkeypatch.setattr(paths, "is_running_on_render", lambda: True)
    monkeypatch.setattr(paths, "get_render_persistent_mount_path", lambda: "/var/data")

    resolved = paths.get_base_data_path()

    assert resolved == str(override_path)
    assert override_path.exists()


def test_get_base_data_path_uses_render_disk_when_available(monkeypatch, tmp_path):
    monkeypatch.delenv("EVOLVIAN_DATA_PATH", raising=False)
    monkeypatch.setattr(paths, "is_running_on_render", lambda: True)
    monkeypatch.setattr(paths, "get_render_persistent_mount_path", lambda: str(tmp_path))

    resolved = paths.get_base_data_path()

    assert resolved == str(tmp_path)


def test_get_base_data_path_falls_back_when_override_is_not_writable(monkeypatch):
    monkeypatch.setenv("EVOLVIAN_DATA_PATH", "/var/data")
    monkeypatch.setattr(paths, "is_running_on_render", lambda: True)
    monkeypatch.setattr(paths, "get_render_persistent_mount_path", lambda: None)

    original_prepare = paths._prepare_writable_path

    def fake_prepare(path_value: str, *, reason: str) -> str | None:
        if path_value == "/var/data":
            return None
        return original_prepare(path_value, reason=reason)

    monkeypatch.setattr(paths, "_prepare_writable_path", fake_prepare)

    resolved = paths.get_base_data_path()

    assert resolved == "/tmp/evolvian_data"


def test_get_base_data_path_falls_back_to_tmp_on_render_without_disk(monkeypatch):
    monkeypatch.delenv("EVOLVIAN_DATA_PATH", raising=False)
    monkeypatch.setattr(paths, "is_running_on_render", lambda: True)
    monkeypatch.setattr(paths, "get_render_persistent_mount_path", lambda: None)

    resolved = paths.get_base_data_path()

    assert resolved == "/tmp/evolvian_data"


def test_get_base_data_path_uses_local_cwd_when_not_on_render(monkeypatch, tmp_path):
    monkeypatch.delenv("EVOLVIAN_DATA_PATH", raising=False)
    monkeypatch.setattr(paths, "is_running_on_render", lambda: False)
    monkeypatch.setattr(paths, "get_render_persistent_mount_path", lambda: None)
    monkeypatch.setattr(paths.os, "getcwd", lambda: str(tmp_path))

    resolved = paths.get_base_data_path()

    assert resolved == str(tmp_path / "data")


def test_get_render_persistent_mount_path_detects_known_mount(monkeypatch, tmp_path):
    monkeypatch.delenv("RENDER_DISK_MOUNT_PATH", raising=False)
    monkeypatch.setattr(paths, "RENDER_DEFAULT_DISK_MOUNTS", (tmp_path,))

    assert paths.get_render_persistent_mount_path() == str(tmp_path)
