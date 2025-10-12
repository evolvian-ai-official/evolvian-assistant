from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()

# 📂 Directorio base de archivos estáticos
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

# ✅ Servir el widget (iframe)
@router.get("/widget.html")
async def serve_widget():
    return FileResponse(
        os.path.join(STATIC_DIR, "widget.html"),
        headers={
            "Content-Security-Policy": "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
        },
        media_type="text/html",
    )

# ✅ Servir el script flotante
@router.get("/embed-floating.js")
async def serve_embed_js():
    return FileResponse(
        os.path.join(STATIC_DIR, "embed-floating.js"),
        headers={"Content-Type": "application/javascript"},
    )

# ✅ Servir CSS flotante (si lo usas)
@router.get("/embed-floating.css")
async def serve_embed_css():
    return FileResponse(
        os.path.join(STATIC_DIR, "embed-floating.css"),
        headers={"Content-Type": "text/css"},
    )
