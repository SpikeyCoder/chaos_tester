---
title: Risk Register
tsc: CC3
owner: Kevin Armstrong
review-cadence: quarterly
last-reviewed: 2026-05-04
---

# Risk Register — website-auditor.io

| ID | Risk | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| R-01 | SSRF on user-supplied URLs (`/run`, `/api/detect-business`) | Medium | High | `safe_http.SafeSession` re-checks every redirect; `_is_private_or_reserved` blocklist | Mitigated |
| R-02 | Resource abuse on open endpoints (`/run`, `/api/bug-report`, `/api/detect-business`) | Medium | Medium | Rate limiting (Flask-Limiter) — see security/2026-05-04-rate-limit | Planned |
| R-03 | Trello card spam from bug-report endpoint | Medium | Low | Same as R-02 | Planned |
| R-04 | wa_auth JWT secret leak | Low | High | Stored only in Cloud Run env; rotated on suspicion | Mitigated |
| R-05 | Subscription bypass on `/api/ai-query` | Low | Medium | wa_auth.is_entitled validates JWT + Supabase subscription state | Mitigated |
| R-06 | Single-owner bus factor | Medium | High | Encrypted credential vault shared with successor designee | Partial |
