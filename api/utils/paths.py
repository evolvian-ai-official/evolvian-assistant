# api/utils/paths.py
import os
import logging

def get_base_data_path() -> str:
    render_root = "/opt/render/project/src"
    base_dir = (
        os.path.join(render_root, "data")
        if os.path.exists(render_root)
        else os.path.join(os.getcwd(), "data")
    )
    os.makedirs(base_dir, exist_ok=True)
    logging.info(f"📂 Base data path usada: {base_dir}")
    return base_dir
