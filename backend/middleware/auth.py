"""FastAPI dependency for Clerk JWT authentication.

Usage in route:
    @router.get("/protected")
    async def protected(user: dict = Depends(require_auth)):
        return {"user_id": user["sub"]}
"""

from typing import Any

from fastapi import Depends, HTTPException, Request

from auth.clerk import ClerkTokenError, verify_clerk_token
from config import settings


def _extract_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header or query param.

    Checks Authorization header first, then falls back to ?token= query
    parameter (needed for EventSource/SSE which can't set custom headers).
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # Fallback: query param for SSE endpoints (EventSource can't set headers)
    token = request.query_params.get("token")
    if token:
        return token
    return None


async def require_auth(request: Request) -> dict[str, Any]:
    """FastAPI dependency — requires a valid Clerk JWT.

    Returns the decoded JWT payload (contains sub, email, etc.).
    Raises 401 if token is missing or invalid.
    """
    # Skip auth for public endpoints
    if request.url.path in settings.PUBLIC_ENDPOINTS:
        return {}

    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required", "code": "UNAUTHENTICATED"},
        )

    try:
        payload = verify_clerk_token(token)
    except ClerkTokenError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": str(e), "code": "INVALID_TOKEN"},
        )

    return payload


async def optional_auth(request: Request) -> dict[str, Any] | None:
    """FastAPI dependency — returns user payload if token present, None otherwise."""
    token = _extract_bearer_token(request)
    if not token:
        return None
    try:
        return verify_clerk_token(token)
    except ClerkTokenError:
        return None
