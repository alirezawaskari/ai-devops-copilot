"""API key authentication.

Keys are supplied via the `X-API-Key` header. Accepted keys come from the
`API_KEYS` setting (comma separated) for local/dev deployments. In production
this should be backed by a proper secrets store, but a static allow-list keeps
the reference implementation dependency-free and easy to reason about.
"""

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    settings = get_settings()

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )

    if x_api_key not in settings.api_key_list:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return x_api_key
