# api/utils/paths.py
import logging
import os
from pathlib import Path


RENDER_SOURCE_ROOT = Path("/opt/render/project/src")
RENDER_DEFAULT_DISK_MOUNTS = (
    Path("/var/data"),
    Path("/data"),
)


def is_running_on_render() -> bool:
    return RENDER_SOURCE_ROOT.exists()


def get_render_persistent_mount_path() -> str | None:
    configured_mount = (os.getenv("RENDER_DISK_MOUNT_PATH") or "").strip()
    candidates = []
    if configured_mount:
        candidates.append(Path(configured_mount))
    candidates.extend(RENDER_DEFAULT_DISK_MOUNTS)

    for candidate in candidates:
        if candidate.is_dir() and os.access(candidate, os.W_OK):
            return str(candidate)

    return None


def _prepare_writable_path(path_value: str, *, reason: str) -> str | None:
    candidate = Path(path_value)

    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logging.warning(
            "⚠️ Data path %s is not writable (%s). Trying the next fallback.",
            candidate,
            reason,
        )
        return None
    except OSError as exc:
        logging.warning(
            "⚠️ Data path %s could not be prepared (%s: %s). Trying the next fallback.",
            candidate,
            reason,
            exc,
        )
        return None

    if not os.access(candidate, os.W_OK):
        logging.warning(
            "⚠️ Data path %s is not writable after creation (%s). Trying the next fallback.",
            candidate,
            reason,
        )
        return None

    return str(candidate)


def get_base_data_path() -> str:
    """
    Resuelve un directorio writable para datos locales (Chroma, etc.).

    Prioridad:
    1) EVOLVIAN_DATA_PATH (override explícito)
    2) Disk persistente montado en Render (por ejemplo /var/data)
    3) /tmp/evolvian_data (fallback seguro en Render/serverless)
    4) <cwd>/data (desarrollo local)
    """
    candidates: list[tuple[str, str]] = []
    override = (os.getenv("EVOLVIAN_DATA_PATH") or "").strip()
    if override:
        candidates.append((override, "explicit_override"))

    render_disk = get_render_persistent_mount_path() if is_running_on_render() else None
    if render_disk:
        candidates.append((render_disk, "render_persistent_disk"))

    if is_running_on_render():
        # En Render el source puede ser read-only en runtime.
        candidates.append(("/tmp/evolvian_data", "render_tmp_fallback"))
    else:
        candidates.append((os.path.join(os.getcwd(), "data"), "local_cwd"))

    seen: set[str] = set()
    for candidate, reason in candidates:
        normalized = str(Path(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)

        prepared = _prepare_writable_path(normalized, reason=reason)
        if prepared:
            logging.info(f"📂 Base data path usada: {prepared}")
            return prepared

    raise RuntimeError("No writable base data path is available.")
