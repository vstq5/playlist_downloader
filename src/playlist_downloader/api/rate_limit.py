from __future__ import annotations

from fastapi import FastAPI
from starlette.requests import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

def _rate_limit_key(request: Request) -> str:
    # Prefer the per-device identifier used for tenant isolation.
    device_id = request.headers.get("x-device-id")
    if device_id:
        return f"device:{device_id}"

    # Fall back to forwarded IP when behind a proxy (Render/Vercel).
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return f"ip:{ip}"

    return f"ip:{get_remote_address(request)}"


# Keep a single limiter instance to match legacy behavior.
limiter = Limiter(key_func=_rate_limit_key)


def init_rate_limiter(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
