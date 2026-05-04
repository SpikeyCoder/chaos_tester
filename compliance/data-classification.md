---
title: Data Classification Standard
tsc: C1, P1
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-04
---

# Data Classification — website-auditor.io

| Class | Examples | Storage |
|---|---|---|
| Public | Reports run by users on their own sites; SEO pages | GitHub, Cloud Run logs (90d) |
| Internal | Run history, run IDs, progress events | Cloud Run instance memory, /reports/*.json (ephemeral) |
| Confidential | Bug-report screenshots, user-supplied URLs (may contain auth-bearing query params) | Trello (encrypted at rest), Cloud Run logs (90d) |
| Restricted | API keys (`PERPLEXITY_API_KEY`, `TRELLO_*`, `GOOGLE_PLACES_API_KEY`, `CHAOS_TESTER_SECRET_KEY`, `WA_SHARED_SECRET`) | Cloud Run env vars only |
