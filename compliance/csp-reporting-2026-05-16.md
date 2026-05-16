---
title: CSP Reporting Endpoint
tsc: CC4.1, CC7.1
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-16
applies-to: website-auditor.io (SpikeyCoder/chaos_tester)
related: csp-hardening-2026-05-15.md
finding-id: WA-2026-05-16-01
---

# CSP Reporting Endpoint — website-auditor.io

## Background

After PR #59 (2026-05-15) the Cloud Run service ships a tight CSP with
the CSP3 carve-out directives in place. The policy was, however,
**unobservable**: a CSP regression in production (e.g. a copy-paste
re-introducing an inline event handler, a third-party CDN script whose
sha256 hash drifts, or an in-browser XSS the policy successfully
blocks) failed silently in the user's browser. The operator had no
signal.

kevinarmstrong.io closed the equivalent gap on 2026-05-15 (PR #34).
This PR brings parity to website-auditor.io.

## Implementation

- The CSP now ends with `report-uri /api/csp-report; report-to csp-endpoint;`.
- A `Reporting-Endpoints: csp-endpoint="/api/csp-report"` header is
  emitted on every response.
- `POST /api/csp-report` accepts both the legacy
  `application/csp-report` body and the modern
  `application/reports+json` batch. The handler logs a single-line JSON
  record (`kind: "csp-report"`) and returns `204`. Cloud Logging is
  the persistent record; Cloud Run is stateless and we do not persist
  payloads in the service itself.
- The endpoint is rate-limited at **60/min, 600/hr** per IP via the
  existing flask-limiter middleware. The cap is well above any
  plausible legitimate violation rate but bounds the cost of a
  hostile flood.
- Bodies above 64 KiB are truncated to keep individual log lines
  bounded; over-long reports are still summarised but cannot blow up
  the log ingestion budget.
- GET / methods other than POST return 405; the global OPTIONS
  preflight handler still answers CORS preflights.

## Verification

```bash
# 1. CSP header carries the new directives
curl -sI https://website-auditor.io/ | grep -i 'content-security-policy\|reporting-endpoints'

# 2. POST is accepted; arbitrary non-JSON is accepted too (browsers send
#    application/csp-report in some cases).
curl -sX POST https://website-auditor.io/api/csp-report \
    -H 'Content-Type: application/csp-report' \
    --data '{"csp-report":{"document-uri":"https://website-auditor.io/","violated-directive":"script-src"}}' \
    -w '%{http_code}\n' -o /dev/null
# → 204

# 3. GET is rejected
curl -s -o /dev/null -w '%{http_code}\n' https://website-auditor.io/api/csp-report
# → 405

# 4. Force a CSP violation in DevTools → Console; observe POST 204 +
#    a {"kind":"csp-report",…} JSON line in Cloud Logging.
```

## References

- W3C — Content Security Policy Level 3: `report-to`, `report-uri`
- W3C — Reporting API: `Reporting-Endpoints` HTTP header
- OWASP Secure Headers Project
- AICPA TSC CC4.1 (monitoring activities), CC7.1 (vulnerability identification)
