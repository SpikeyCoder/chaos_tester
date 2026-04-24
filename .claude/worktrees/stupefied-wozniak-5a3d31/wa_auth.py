"""
Cross-subdomain authentication gate for website-auditor.io.

The admin portal at api.website-auditor.io mints an HMAC-signed JWT after a
user successfully authenticates (Google OAuth or Supabase magic link) and
sets it as a session cookie scoped to ``.website-auditor.io`` under the
name ``wa_auth``. The main site reads that cookie on every /report render
and on every call to /api/ai-query to decide whether the custom AI
Visibility search is available.

This module is deliberately thin: it verifies the JWT, pulls the
``api_users.id`` out of the ``sub`` claim, and asks supabase_client for a
live subscription row. Identity lives in the cookie, entitlement lives in
Supabase — so a cancelled trial locks the user out on the next page load
without needing to invalidate the cookie.

The shared secret must be the same value in both the Node admin portal
(``WA_SHARED_SECRET`` env var) and this Flask app.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import jwt

from . import supabase_client as supa

logger = logging.getLogger("chaos_tester.wa_auth")

_COOKIE_NAME = "wa_auth"
_JWT_ALG = "HS256"


def _shared_secret() -> str:
    """Return the shared HMAC secret, or empty string if unset."""
    return os.environ.get("WA_SHARED_SECRET", "")


def _decode_token(token: str) -> Optional[dict]:
    """Verify the JWT signature and return its payload, or None on failure."""
    secret = _shared_secret()
    if not secret:
        logger.warning("WA_SHARED_SECRET not set — cannot verify wa_auth cookie")
        return None
    try:
        return jwt.decode(token, secret, algorithms=[_JWT_ALG])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_entitlement(request) -> Optional[dict]:
    """
    Return an entitlement dict if the caller is authenticated AND currently
    on an active or trialing subscription, otherwise None.

    Shape on success::

        {
            "user_id": "<api_users.id>",
            "subscription": {
                "status": "trialing" | "active",
                "current_period_end": "...",
                "trial_end": "..."
            }
        }

    None means "show the upsell banner / block the API call."
    """
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return None

    payload = _decode_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    sub = supa.get_active_subscription(user_id)
    if not sub:
        return None

    return {"user_id": user_id, "subscription": sub}


def is_entitled(request) -> bool:
    """Convenience wrapper that returns only the boolean."""
    return get_current_entitlement(request) is not None
