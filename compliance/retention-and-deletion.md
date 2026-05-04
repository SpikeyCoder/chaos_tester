---
title: Data Retention & Deletion Policy
tsc: C1, P4
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-04
---

# Retention & Deletion — website-auditor.io

| Dataset | Retention | Deletion mechanism |
|---|---|---|
| `/reports/*.json` (per-run results) | Until container restart (ephemeral) | Automatic |
| Cloud Run request/error logs | 90 days (Cloud Run default) | Automatic |
| Trello bug-report cards | 12 months | Manual archival |
| GitHub repo + Actions logs | Indefinite (source); 90 days (Actions) | GitHub default |

User-data subject requests (access / deletion) are handled by emailing
`kevinmarmstrong1990@gmail.com`; SLA is 30 days.
