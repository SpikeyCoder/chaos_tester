# Security Policy

## Supported Versions

The Website Auditor service at [website-auditor.io](https://website-auditor.io)
runs from this repository's `main` branch on Google Cloud Run, with the
public dashboard hosted via GitHub Pages. Only `main` is actively
maintained.

## Reporting a Vulnerability

**Please do not file public GitHub issues for security vulnerabilities.**

Email **kevinmarmstrong1990@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept (text only — do not attach
  exploit binaries)
- Any relevant logs, screenshots, or code references

You can expect an acknowledgement within **48 hours** and an initial
status update within **7 days**. Critical findings (RCE, auth bypass,
SSRF that bypasses the existing guards, sensitive data exposure) are
triaged ahead of routine work.

## Scope

In scope:

- Authentication or authorization bypass on `api.website-auditor.io`
  flows surfaced through the dashboard
- Server-Side Request Forgery (CWE-918) bypassing `safe_http.SafeSession`
  and `config._is_private_or_reserved`
- Cross-Site Scripting (XSS) on `website-auditor.io` rendered content
- Cross-Site Request Forgery (CSRF) on any state-changing endpoint
- Supply-chain issues in pinned third-party dependencies (pip + the
  small CDN-loaded JS libraries used by the dashboard)

Out of scope:

- Denial-of-service (resource-consumption testing) — please report
  rate-limiting gaps as findings, but do not exercise them at volume
- Self-XSS that requires a user to paste code into devtools
- Issues that require physical access to a device
- The `/api/ai-query` subscription gate is **intentional**; bypass
  attempts on the open endpoints (`/run`, `/api/runs`,
  `/api/detect-business`, `/api/bug-report`) are out of scope because
  those endpoints are by design open

## Architecture Notes for Researchers

- **Backend**: Flask app on Google Cloud Run, behind a same-origin
  request gate (`X-Requested-With: XMLHttpRequest`).
- **Frontend**: static dashboard served via GitHub Pages →
  `website-auditor.io`.
- **Subscription gating**: `/api/ai-query` validates a `wa_auth` cookie
  minted by the separate `api.website-auditor.io` admin portal (HS256
  JWT, `WA_SHARED_SECRET`). All other endpoints are intentionally open.
- **SSRF defence**: `safe_http.SafeSession` re-validates every redirect
  hop; the same hostname check (`config._is_private_or_reserved`) gates
  the entrypoint.
- **CSRF defence**: form-encoded POSTs validate a per-session token;
  JSON POSTs require `X-Requested-With`.
- **Secrets**: `CHAOS_TESTER_SECRET_KEY`, `PERPLEXITY_API_KEY`,
  `TRELLO_*`, `GOOGLE_PLACES_API_KEY`, and `WA_SHARED_SECRET` are
  deployed as Cloud Run env vars and never reach the dashboard.

## Safe Harbor

Armstrong HoldCo LLC will not pursue legal action against researchers
who:

- Make a good-faith effort to comply with this policy
- Avoid privacy violations, denial-of-service, and destructive testing
- Give a reasonable disclosure window before going public

Thank you for helping keep the Website Auditor and Armstrong HoldCo LLC
customers safe.
