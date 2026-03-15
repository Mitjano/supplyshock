"""Clerk JWT verification via JWKS.

Fetches Clerk's public keys once, caches them, and verifies
incoming Bearer tokens on every protected request.
"""

import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from config import settings

# Default JWKS URL placeholder — overridden by CLERK_JWKS_URL env var or
# derived at runtime from the publishable key when available.
_DEFAULT_JWKS_URL = "https://clerk.example.com/.well-known/jwks.json"


def _derive_jwks_url() -> str:
    """Build Clerk JWKS URL from publishable key (pk_test_xxx or pk_live_xxx)."""
    pk = settings.CLERK_PUBLISHABLE_KEY
    if pk and "_" in pk:
        parts = pk.split("_")
        if len(parts) >= 3:
            # pk_test_abcdef... → abcdef...
            instance_id = "_".join(parts[2:])
            return f"https://{instance_id}.clerk.accounts.dev/.well-known/jwks.json"
    return _DEFAULT_JWKS_URL

# Cache JWKS client (handles key rotation automatically)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # Clerk's JWKS URL — prefer explicit env var, fall back to derived
        jwks_url = settings.CLERK_JWKS_URL if settings.CLERK_JWKS_URL else _derive_jwks_url()
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return _jwks_client


class ClerkTokenError(Exception):
    """Raised when a Clerk JWT cannot be verified."""


def verify_clerk_token(token: str) -> dict[str, Any]:
    """Verify a Clerk JWT and return the decoded payload.

    Returns dict with at minimum: sub (clerk_user_id), email, exp, iat.
    Raises ClerkTokenError on any verification failure.
    """
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["sub", "exp", "iat"],
            },
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ClerkTokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ClerkTokenError(f"Invalid token: {e}")
    except Exception as e:
        raise ClerkTokenError(f"Token verification failed: {e}")
