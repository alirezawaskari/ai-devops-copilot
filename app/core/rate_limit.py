"""Redis-backed fixed-window rate limiting middleware.

Each API key (or client IP, if unauthenticated) gets `RATE_LIMIT_REQUESTS`
requests per `RATE_LIMIT_WINDOW_SECONDS`. Implemented as a fixed window
counter in Redis using INCR + EXPIRE, which is O(1) per request and simple
enough to audit at a glance.
"""

import time

from fastapi import Request, Response, status
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, redis_client: Redis) -> None:
        super().__init__(app)
        self._redis = redis_client
        self._settings = get_settings()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        identity = request.headers.get("x-api-key") or (request.client.host if request.client else "anonymous")
        window = int(time.time()) // self._settings.rate_limit_window_seconds
        key = f"ratelimit:{identity}:{window}"

        current = await self._redis.incr(key)
        if current == 1:
            await self._redis.expire(key, self._settings.rate_limit_window_seconds)

        if current > self._settings.rate_limit_requests:
            return Response(
                content='{"detail":"Rate limit exceeded."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )

        return await call_next(request)
