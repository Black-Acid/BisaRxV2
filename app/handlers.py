from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

async def _rate_limit_exceeded_handler(request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."}
    ) 