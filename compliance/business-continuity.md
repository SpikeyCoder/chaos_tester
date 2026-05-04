---
title: Business Continuity & Disaster Recovery
tsc: A, CC9
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-04
---

# Business Continuity & DR — website-auditor.io

## Recovery objectives
| System | RTO | RPO |
|---|---|---|
| Cloud Run service | 1 hour (rebuild from main) | 0 (git is source of truth) |
| Trello workspace | n/a (Trello is system of record) | n/a |
| Perplexity / Google Places | n/a (3rd-party APIs; degraded mode shows clear errors) | n/a |

## Backup / state
The service is intentionally stateless beyond ephemeral `/reports/*.json`
which are regenerated per run. There are no persistent customer datasets
to back up.

## Failure scenarios
| Scenario | Detection | Recovery |
|---|---|---|
| Cloud Run outage | StatusGator alert | Wait or fail over to local docker compose for pen-test customers |
| Trello outage | Bug-report failures in logs | Disable the bug-report button via feature flag |
| Perplexity outage | `/api/ai-query` returns 503 | Display "AI provider unavailable" banner |
