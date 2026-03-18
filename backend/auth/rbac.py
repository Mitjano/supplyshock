"""Role-based access control helpers.

Derives user plan from JWT metadata or DB lookup.
Used by rate_limit.py and billing endpoints.
"""

from typing import Any


def _get_user_plan(user: dict[str, Any]) -> str:
    """Extract user plan from JWT payload or DB-injected field.

    Checks (in order):
    1. _db_plan — injected by resolve_user_id()
    2. Clerk public metadata — user.public_metadata.plan
    3. Default: "free"
    """
    # From DB (injected by resolve_user_id)
    if "_db_plan" in user:
        return user["_db_plan"]

    # From Clerk JWT metadata
    public_metadata = user.get("public_metadata", {})
    if isinstance(public_metadata, dict):
        plan = public_metadata.get("plan")
        if plan:
            return plan

    return "free"
