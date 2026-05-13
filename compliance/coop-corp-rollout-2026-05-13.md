# COOP / CORP / FLoC opt-out rollout — 2026-05-13

## Background

Pen-test 2026-05-13 findings **WA-2026-05-13-01** (interest-cohort opt-out
missing) and **WA-2026-05-13-02** (no `Cross-Origin-Opener-Policy` /
`Cross-Origin-Resource-Policy` headers on the Flask response bundle).

Before this change the response headers shipped:

* `Permissions-Policy: camera=(), microphone=(), geolocation=()`
* CSP `frame-ancestors 'none'` (clickjacking)
* No COOP / CORP / COEP

That leaves two gaps:

1. **FLoC / Topics**: without `interest-cohort=()` in Permissions-Policy
   the origin is implicitly opted into Chrome's cohort calculation,
   exposing user-segment data on a privacy-sensitive admin tool.
2. **Cross-origin isolation**: the document is reachable via
   `window.open` from third-party origins under the same browsing
   context group, which keeps `window.opener` references alive after
   the navigation — relevant for the AI-Visibility upsell hop to
   `api.website-auditor.io`.

## Decision

* Add `interest-cohort=()` to Permissions-Policy.
* Add `Cross-Origin-Opener-Policy: same-origin`.
* Add `Cross-Origin-Resource-Policy: same-origin`.

COEP is deliberately **not** added in this PR. The dashboard pulls
analytics from `website-auditor.goatcounter.com` and Google Maps tiles
from `maps.googleapis.com`; neither emits CORP today, so COEP
`require-corp` would break them. Once those vendors emit CORP, a
follow-up PR can layer COEP for full cross-origin isolation.

## Verification

1. Build and ship to Cloud Run preview.
2. `curl -sI https://<preview-run-url>/` shows the three new headers.
3. Load the dashboard, run an audit, and confirm:
   * No console errors.
   * Goatcounter beacon still fires.
   * Google Maps preview still renders on the business-detect step.
4. `window.opener` from a popup is `null` (COOP working).

## Reference

* OWASP Secure Headers Project — COOP, CORP
* MDN — `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`
* WICG Privacy CG — `Permissions-Policy: interest-cohort`
