# api/blog/service.py
from api.modules.assistant_rag.supabase_client import supabase



def save_comment(data: dict):
    """Guarda un comentario en Supabase."""
    res = supabase.table("public_blog_comments").insert(data).execute()
    return res

def list_comments(slug: str):
    """Devuelve los comentarios aprobados de un post."""
    res = (
        supabase.table("public_blog_comments")
        .select("*")
        .eq("post_slug", slug)
        .eq("is_approved", True)
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []
