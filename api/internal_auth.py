import hmac
import os

from fastapi import HTTPException, Request, status


INTERNAL_TASK_TOKEN_ENV = "EVOLVIAN_INTERNAL_TASK_TOKEN"
INTERNAL_TASK_HEADER = "x-evolvian-internal-token"


def _get_expected_internal_token() -> str:
    return (os.getenv(INTERNAL_TASK_TOKEN_ENV) or "").strip()


def has_valid_internal_token(request: Request, *, strict: bool = False) -> bool:
    expected = _get_expected_internal_token()
    if not expected:
        if strict:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="internal_task_token_not_configured",
            )
        return False

    provided = (request.headers.get(INTERNAL_TASK_HEADER) or "").strip()
    return bool(provided) and hmac.compare_digest(provided, expected)


def require_internal_request(request: Request) -> None:
    if not has_valid_internal_token(request, strict=True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_internal_task_token",
        )
