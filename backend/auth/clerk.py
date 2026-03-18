"""Clerk JWT verification.

Verifies JWTs issued by Clerk using JWKS (JSON Web Key Set).
Clerk publishes its public keys at the JWKS endpoint.
"""

import logging
from functools import lru_cache

import jwt
import requests

from config import settings

logger = logging.getLogger("auth.clerk")


class ClerkTokenError(Exception):
    """Raised when Clerk JWT verification fails."""
    pass


@lru_cache(maxsize=1)
def _get_jwks_client() -> jwt.PyJWKClient:
    """Get cached JWKS client for Clerk token verification."""
    jwks_url = settings.CLERK_JWKS_URL
    if not jwks_url and settings.CLERK_PUBLISHABLE_KEY:
        # Derive JWKS URL from publishable key
        # Format: pk_test_xxx or pk_live_xxx
        # JWKS URL: https://{instance}.clerk.accounts.dev/.well-known/jwks.json
        # For simplicity, use the Clerk Frontend API
        pk = settings.CLERK_PUBLISHABLE_KEY
        if pk.startswith("pk_"):
            # Extract the instance identifier
            parts = pk.split("_", 2)
            if len(parts) >= 3:
                instance_id = parts[2]
                jwks_url = f"https://{instance_id}.clerk.accounts.dev/.well-known/jwks.json"

    if not jwks_url:
        raise ClerkTokenError("CLERK_JWKS_URL not configured")

    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk JWT and return the decoded payload.

    Args:
        token: Raw JWT string from Authorization header.

    Returns:
        Decoded JWT payload dict (contains sub, email, etc.).

    Raises:
        ClerkTokenError: If token is invalid, expired, or verification fails.
    """
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,  # Clerk doesn't always set aud
            },
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise ClerkTokenError("Token expired")
    except jwt.InvalidTokenError as e:
        raise ClerkTokenError(f"Invalid token: {e}")
    except Exception as e:
        logger.error("Clerk token verification failed: %s", e)
        raise ClerkTokenError("Token verification failed")
