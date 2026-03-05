# api/utils/paths.py
import os
import logging


def get_base_data_path() -> str:
    """
    Resuelve un directorio writable para datos locales (Chroma, etc.).

    Prioridad:
    1) EVOLVIAN_DATA_PATH (override explícito)
    2) RENDER_DISK_MOUNT_PATH/data (si hay disco persistente en Render)
    3) /tmp/evolvian_data (fallback seguro en Render/serverless)
    4) <cwd>/data (desarrollo local)
    """
    override = (os.getenv("EVOLVIAN_DATA_PATH") or "").strip()
    if override:
        base_dir = override
    else:
        render_disk = (os.getenv("RENDER_DISK_MOUNT_PATH") or "").strip()
        if render_disk:
            base_dir = os.path.join(render_disk, "data")
        elif os.path.exists("/opt/render/project/src"):
            # En Render el source puede ser read-only en runtime.
            base_dir = "/tmp/evolvian_data"
        else:
            base_dir = os.path.join(os.getcwd(), "data")

    os.makedirs(base_dir, exist_ok=True)
    logging.info(f"📂 Base data path usada: {base_dir}")
    return base_dir
