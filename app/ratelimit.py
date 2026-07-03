import time

from fastapi import HTTPException, Request

from app.config import get_settings

_hits: dict[str, list[float]] = {}
_WINDOW = 60.0


def rate_limit(request: Request) -> None:
    limit = get_settings().rate_limit_max
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < _WINDOW]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    recent.append(now)
    _hits[ip] = recent
