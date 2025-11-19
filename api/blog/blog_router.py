# api/blog/blog_router.py
from fastapi import APIRouter, HTTPException, Request, Query, Body
from .models import CommentPayload
from .service import save_comment, list_comments
from api.modules.assistant_rag.supabase_client import supabase

router = APIRouter(prefix="/api/blog", tags=["Blog"])

print("✅ blog_router imported successfully")

# ============================================================
# 🗨️ 1. Obtener comentarios aprobados
# ============================================================
@router.get("/comments")
def get_comments(slug: str = Query(...)):
    """
    Devuelve los comentarios aprobados de un post público.
    """
    try:
        data = list_comments(slug)  # ← list_comments ya usa public_blog_comments
        return {"comments": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 💬 2. Enviar comentario nuevo
# ============================================================
@router.post("/comments")
def post_comment(payload: CommentPayload, request: Request):
    try:
        ip = request.client.host
        ua = request.headers.get("user-agent")

        # ===============================
        # NUEVOS CAMPOS YA INCLUIDOS
        # ===============================
        data = {
            "post_slug": payload.post_slug.strip(),
            "name": payload.name.strip(),
            "email": payload.email.strip().lower(),
            "comment": payload.comment.strip(),
            "wants_news": payload.wants_news,
            "accepted_terms": payload.accepted_terms,  # ✔ NUEVO
            "phone": payload.phone,                    # ✔ NUEVO
            "accepted_privacy_policy": payload.accepted_privacy_policy,
            "ip_address": ip,
            "user_agent": ua,
            "is_approved": False,  # moderación manual
        }

        save_comment(data)  # ← Esto guarda en public_blog_comments

        # =====================================================
        # 📨  Registrar newsletter si aceptó marketing
        # =====================================================
        if payload.wants_news:
            existing = (
                supabase.table("newsletter_subscribers")
                .select("id")
                .eq("email", payload.email.strip().lower())
                .execute()
            )

            if not existing.data:
                supabase.table("newsletter_subscribers").insert(
                    {
                        "name": payload.name.strip(),
                        "email": payload.email.strip().lower(),
                        "source": "blog",
                        "ip_address": ip,
                        "user_agent": ua,
                    }
                ).execute()
                print(f"🆕 Newsletter subscriber added: {payload.email}")
            else:
                print(f"ℹ️ Subscriber already exists: {payload.email}")

        return {"message": "✅ Comentario enviado, pendiente de aprobación."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

