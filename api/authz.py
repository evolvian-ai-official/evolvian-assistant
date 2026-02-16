import os
from typing import Optional

import requests
from fastapi import HTTPException, Request, status

from api.modules.assistant_rag.supabase_client import supabase


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def _extract_bearer_token(request: Request) -> str:
    auth_header: Optional[str] = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
        )
    return auth_header.split(" ", 1)[1].strip()


def get_current_user_id(request: Request) -> str:
    cached = getattr(request.state, "auth_user_id", None)
    if cached:
        return cached

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth_not_configured",
        )

    token = _extract_bearer_token(request)

    try:
        resp = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
            },
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_auth_token",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_auth_token",
        )

    user_id = (resp.json() or {}).get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_auth_token",
        )

    request.state.auth_user_id = user_id
    return user_id


def assert_client_ownership(client_id: str, auth_user_id: str) -> None:
    res = (
        supabase.table("clients")
        .select("id")
        .eq("id", client_id)
        .eq("user_id", auth_user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden_client_access",
        )


def authorize_client_request(request: Request, client_id: str) -> str:
    auth_user_id = get_current_user_id(request)
    assert_client_ownership(client_id, auth_user_id)
    return auth_user_id
