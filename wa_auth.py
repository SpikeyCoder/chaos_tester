from __future__ import annotations

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

import logging
import os
from typing import Optional

import jwt

from . import supabase_client as supa

logger = logging.getLogger("chaos_tester.wa_auth")

_COOKIE_NAME = "wa_auth"
_JWT_ALG = "HS256"

# Auth-check outcomes returned by ``check_request``. Routes use these to
# decide between 401 (cookie present but unusable -> tell the user to log
# in again) and 403 (authenticated but unentitled -> show upsell).
STATUS_OK = "ok"
STATUS_NO_COOKIE = "no_cookie"
STATUS_SESSION_EXPIRED = "session_expired"
STATUS_NO_SUBSCRIPTION = "no_subscription"


def _shared_secret() -> str:
    """Return the shared HMAC secret, or empty string if unset."""
    return os.environ.get("WA_SHARED_SECRET", "")


def _decode_token(token: str) -> Optional[dict]:
    """Verify the JWT signature and return its payload, or None on failure.

    Treats every non-decodable case as ``None`` for callers that don't care
    *why* the token is bad. Use ``check_request`` when the distinction
    between "expired/invalid cookie" and "no cookie at all" matters.
    """
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
    _, ent = check_request(request)
    return ent


def is_entitled(request) -> bool:
    """Convenience wrapper that returns only the boolean."""
    return get_current_entitlement(request) is not None


def check_request(request):
    """Inspect the wa_auth cookie and return ``(status, entitlement)``.

    ``status`` is one of the ``STATUS_*`` constants:

      - ``STATUS_OK``                 caller is authenticated and entitled
      - ``STATUS_NO_COOKIE``          no wa_auth cookie at all
      - ``STATUS_SESSION_EXPIRED``    cookie present but expired or invalid
      - ``STATUS_NO_SUBSCRIPTION``    cookie valid but no active subscription

    The ``entitlement`` dict is only populated for ``STATUS_OK``.

    Distinguishing "no cookie / expired" from "no subscription" lets routes
    return 401 (re-login) vs 403 (upsell) appropriately.
    """
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return STATUS_NO_COOKIE, None

    payload = _decode_token(token)
    if not payload:
        return STATUS_SESSION_EXPIRED, None

    user_id = payload.get("sub")
    if not user_id:
        return STATUS_SESSION_EXPIRED, None

    sub = supa.get_active_subscription(user_id)
    if not sub:
        return STATUS_NO_SUBSCRIPTION, None

    return STATUS_OK, {"user_id": user_id, "subscription": sub}
