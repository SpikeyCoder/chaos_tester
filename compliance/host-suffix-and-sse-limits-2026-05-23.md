# X-Forwarded-Host strict allowlist + SSE rate-limit — 2026-05-23

## WA-2026-05-23-03 — X-Forwarded-Host suffix bypass (MEDIUM)
**OWASP A01:2021, CWE-20, CWE-601**

The `/report/<run_id>` view assembled a public-facing return-URL using:
```
forwarded_host = request.headers.get("X-Forwarded-Host", "").split(",")[0].strip()
if forwarded_host and forwarded_host.endswith("website-auditor.io"):
    public_host = forwarded_host
```
Because `"evilwebsite-auditor.io".endswith("website-auditor.io")` is
`True`, a caller able to set `X-Forwarded-Host` could redirect the
upsell `return_to` URL — and the Stripe-portal `return_to` query
parameter that consumes it — to attacker-controlled phishing
infrastructure.

**Fix:** strict allowlist `{"website-auditor.io", "www.website-auditor.io"}`,
case-insensitive. Falls through to the hardcoded canonical host.

## WA-2026-05-23-04 — Unauthenticated SSE stream had no throttle or lifetime cap (LOW)
**CWE-400 Uncontrolled Resource Consumption**

`/stream` is open to anonymous clients. With gunicorn `--threads 8`,
eight long-lived SSE connections from a single attacker IP could
saturate one Cloud Run instance.

**Fix:** add `@limiter.limit("5 per minute")` to the `stream` route and
hard-cap each connection at 600 seconds.

## Verification
- `curl -H 'X-Forwarded-Host: evilwebsite-auditor.io' .../report/<id>` →
  rendered link must contain `website-auditor.io`, not `evilwebsite-...`.
- `curl -N .../stream`, kept open, must close at ~600s.
- Six rapid `/stream` requests from the same IP must yield 429 on the
  sixth.

Owner: @SpikeyCoder · Effort: S · Priority: P1
