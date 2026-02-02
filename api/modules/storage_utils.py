# api/modules/storage_utils.py
from api.config.config import supabase

def get_signed_url(storage_path: str, expires: int = 3600) -> str:
    res = supabase.storage.from_("evolvian-documents").create_signed_url(
        storage_path,
        expires
    )

    if not res or not res.get("signedURL"):
        raise RuntimeError(f"Failed to sign URL for {storage_path}")

    return res["signedURL"]
