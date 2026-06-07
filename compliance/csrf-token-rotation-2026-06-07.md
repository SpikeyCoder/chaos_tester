# CSRF Token Rotation Cadence — WA-2026-06-06-03 closeout

**Date:** 2026-06-07
**Finding:** WA-2026-06-06-03 (Informational) — "session-bound CSRF token rotation cadence not documented"
**Status:** Closed (policy doc)

## Current implementation

`chaos_tester/app.py::_generate_csrf_token()` lazily mints a 32-byte
`secrets.token_hex` per-session token and stores it in `session["csrf_token"]`.
`_validate_csrf_token()` consumes it via `hmac.compare_digest` and aborts
403 on mismatch. The token is bound to the Flask session cookie
(`SESSION_COOKIE_SECURE = True`, `HTTPONLY`, `SAMESITE=Lax`).

## Rotation cadence (formalised)

1. **Per-session** — A new token is minted automatically the first time
   `_generate_csrf_token()` is called within a session.

2. **On authentication state change** — Today the app has no first-party
   sign-in form; auth lives at `api.website-auditor.io` and is verified
   on every gated call via `wa_auth.is_entitled()`. If a first-party
   sign-in is ever added, the session token MUST be rotated on the
   first request after a successful login or after a logout. Add to
   the sign-in handler:

   ```python
   session.regenerate()  # Flask >= 2.4
   _generate_csrf_token()
   ```

3. **On session expiry** — Flask's default permanent-session lifetime
   is 31 days. The CSRF token rotates implicitly when the session
   cookie expires and the next request mints a new session.

4. **On suspected exposure** — On any CSP report indicating a script
   loaded from outside the strict `script-src` allowlist, treat the
   session as compromised. Operators should clear the session
   cookie's signing key (rotate `CHAOS_TESTER_SECRET_KEY` in Cloud
   Run secret manager) to invalidate every outstanding token. This is
   the same control plane already documented in
   `secret-manager-migration-2026-05-28.md`.

## Verification

- Manual: log out / log back in (when first-party auth lands) →
  cookie's `Set-Cookie: session=...` carries a different value, and
  the `<input name="csrf_token">` rendered on the next page differs
  from the previous one.
- Automated: the unit test `tests/test_csrf_rotation.py` (to add
  alongside the first-party sign-in PR) asserts a new token on
  session regeneration.

## References

- OWASP Cheat Sheet: Cross-Site Request Forgery Prevention
- CWE-352 — Cross-Site Request Forgery (CSRF)
- `compliance/access-review.md` — session-cookie hardening posture
- `compliance/secret-manager-migration-2026-05-28.md` — rotation of
  `CHAOS_TESTER_SECRET_KEY` invalidates all outstanding tokens.
