---
title: API access-tier matrix — chaos_tester (website-auditor.io)
tsc: CC6.1, CC6.2, CC6.3
owner: Kevin Armstrong
review-cadence: quarterly
last-reviewed: 2026-05-14
relates-to: app.py, wa_auth.py
---

# API access-tier matrix

Documents the intentional access-control tiers for every public route in
the `chaos_tester` Flask service. SOC 2 auditors and security
researchers should consult this matrix before flagging the absence of
authentication on the open endpoints — those endpoints are open **by
design** and their compensating controls (CSRF gating, per-IP rate
limits, SSRF guards) are listed below.

## Tier definitions

- **Open.** No authentication. Compensating controls: rate limit + CSRF
  preflight header (`X-Requested-With`) + body size limits + SSRF
  guard (`safe_http.SafeSession` + `config._is_private_or_reserved`).
- **Subscription-gated.** Requires a valid `wa_auth` JWT cookie scoped
  to `.website-auditor.io` **and** an active/trialing subscription in
  Supabase (`wa_auth.is_entitled`).
- **Internal.** Not exposed publicly (no route handler).

## Route matrix

| Route | Method | Tier | Rate limit | CSRF | Notes |
|---|---|---|---|---|---|
| `/` | GET | Open | default 120/min | n/a | Dashboard SPA shell |
| `/run` | POST | Open | 3/min | X-Requested-With + form CSRF | Starts an audit run |
| `/progress`, `/stream` | GET | Open | default | n/a | SSE progress stream for current run |
| `/report/<run_id>` | GET | Open | default | n/a | Report viewer (run_id regex-validated) |
| `/report/<run_id>/json` | GET | Open | default | n/a | Run report as JSON |
| `/report/<run_id>/download/(json\|csv)` | GET | Open | default | n/a | Run report download |
| `/api/runs` | GET | Open | default | X-Requested-With | List recent runs |
| `/api/detect-business` | POST | Open | 10/min, 100/hr | X-Requested-With | Google Places lookup |
| `/api/bug-report` | POST | Open | 5/min, 30/hr | X-Requested-With | Bug-report ingestion |
| **`/api/ai-query`** | POST | **Subscription-gated** | default | X-Requested-With | `wa_auth.is_entitled()` required |
| `/api/psi-status` | GET | Subscription-gated | default | X-Requested-With | Mirrors `/api/ai-query` gate |
| `/.well-known/security.txt` | GET | Open | default | n/a | RFC 9116 disclosure |
| `/robots.txt`, `/sitemap.xml`, `/sample-report`, `/api`, `/about`, `/contact`, `/privacy`, `/terms`, `/status`, `/changelog` | GET | Open | default | n/a | Public site pages |

## Compensating-control summary

1. **CSRF protection (custom header).** Every state-changing endpoint
   requires `X-Requested-With: XMLHttpRequest`. The header triggers a
   CORS preflight that cross-origin attackers cannot satisfy without
   the user's explicit origin allowlist, so it functions as a
   browser-enforced CSRF gate without requiring a per-session token.
2. **CSRF protection (token).** Form-encoded `/run` POSTs additionally
   carry an HMAC-checked per-session CSRF token (`_validate_csrf_token`).
3. **Per-IP rate limits.** `flask_limiter.Limiter` caps abusive
   callers; tighter limits on `/run`, `/api/bug-report`, and
   `/api/detect-business` keep cost-amplifying endpoints behind a
   per-IP budget.
4. **SSRF defence.** `safe_http.SafeSession.send()` re-checks the
   resolved hostname on every outbound request (including redirects)
   and refuses private / loopback / link-local / reserved / cloud-metadata
   addresses. The initial `base_url` is validated again in
   `ChaosConfig.validate()` before a run begins.
5. **Path-traversal defence.** `_validate_run_id()` regex-rejects any
   `run_id` that contains characters outside `[a-zA-Z0-9_-]`, so the
   `/report/<run_id>/...` family of routes cannot be coerced into
   reading filesystem paths outside `REPORTS_DIR`.

## Why `/api/ai-query` is the only gated endpoint

The bearer-token-gated API for paying customers lives in the
**separate** `website-auditor-api` repo (Cloud Run service at
`api.website-auditor.io`). The Flask app in this repo is the public
dashboard and the open audit runner; only the AI Visibility feature is
gated here because it consumes paid third-party API credits
(Perplexity, Google Places). All other endpoints are intentionally
open and protected only by the compensating controls above.

## SOC 2 TSC mapping

- **CC6.1 — Logical access security.** Subscription-gated endpoints
  enforce identity (`wa_auth` JWT) and authorisation (`is_entitled`
  Supabase lookup). Open endpoints document their compensating
  controls in lieu of authentication.
- **CC6.2 — Logical access provisioning / de-provisioning.** Cancelled
  trials lock users out on the next page load because entitlement is
  looked up live in Supabase, not encoded in the cookie.
- **CC6.3 — Logical access removal.** Same as CC6.2 — the cookie is
  identity-only; entitlement is queried per request.

## Change log

- 2026-05-14 — Matrix created. Documents the intentional access-tier
  design called out in the 2026-05-14 pen-test review so future audits
  do not re-flag the open endpoints as findings.
