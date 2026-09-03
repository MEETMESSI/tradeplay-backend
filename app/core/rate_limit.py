import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


# -------------------------------------------------
# Rate limit configuration
# -------------------------------------------------

RATE_LIMITS = {
    "/auth/login": (5, 60),
    "/auth/signup": (5, 60),
    "/auth/refresh": (10, 60),
    "/auth/logout": (10, 60),
    "/auth/logout-all": (10, 60),
}


# -------------------------------------------------
# Request history
# -------------------------------------------------

request_history = defaultdict(deque)


# -------------------------------------------------
# Rate limit middleware
# -------------------------------------------------

async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path

    # Only rate-limit configured endpoints
    if path not in RATE_LIMITS:
        return await call_next(request)

    # Identify client
    client_ip = request.client.host if request.client else "unknown"

    key = f"{client_ip}:{path}"

    max_requests, window_seconds = RATE_LIMITS[path]

    now = time.time()

    requests = request_history[key]

    # Remove requests outside the current window
    while requests and requests[0] <= now - window_seconds:
        requests.popleft()

    # Check limit
    if len(requests) >= max_requests:
        retry_after = int(
            window_seconds - (now - requests[0])
        ) + 1

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please try again later."
            },
            headers={
                "Retry-After": str(retry_after)
            },
        )

    # Record request
    requests.append(now)

    return await call_next(request)