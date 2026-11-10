import secrets

from fastapi import Header, HTTPException

from app.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().api_key
    if not expected:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "A valid X-API-Key header is required for this request.",
            },
        )
