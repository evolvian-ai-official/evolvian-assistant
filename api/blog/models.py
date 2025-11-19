# api/blog/models.py
from pydantic import BaseModel, EmailStr

class CommentPayload(BaseModel):
    """Esquema del comentario enviado desde el blog público."""
    post_slug: str
    name: str
    email: EmailStr
    comment: str
    wants_news: bool = False

    # 🆕 Campos añadidos
    accepted_terms: bool = False
    phone: str | None = None
    accepted_privacy_policy: bool = False
