---
title: Data Subject Access Request (DSAR) Runbook — website-auditor.io
tsc: P5 (Privacy)
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-20
---

# DSAR Runbook (website-auditor.io)

## Scope

This runbook governs how the **website-auditor.io** service responds to
data-subject rights requests made under GDPR (Articles 15–22), CCPA, and
state-equivalents (CPRA, VCDPA, CPA, CTDPA, UCPA).

The service is largely stateless: scan reports are keyed by a random
`run_id` and the only identifiable data the platform retains is:

| Data class            | Where stored                                | Retention |
| --------------------- | ------------------------------------------- | --------- |
| Scan report (run_id)  | Supabase `audit_runs` table + Cloud Storage | 90 days   |
| Bug-report submission | Trello board `Website Auditor Bugs`         | 365 days  |
| Subscription record   | api.website-auditor.io (separate repo)      | 7 years   |
| Access log            | Cloud Run / GCS structured logs             | 30 days   |

## How a request arrives

Requests must be sent to **kevinmarmstrong1990@gmail.com** with the
subject line beginning `DSAR:`. Requests received through any other
channel are forwarded to that address.

## Verification

1. Confirm the requester's identity (email reply-to + one of: the
   browser session cookie value used at the time of the scan, the
   Trello card ID for a bug report, the Stripe customer ID for a
   subscription).
2. If verification fails, respond declining the request and explaining
   what is required (do not delete data on an unverified request).

## Fulfillment

| Right                 | Action                                                                                                    | Owner            | SLA       |
| --------------------- | --------------------------------------------------------------------------------------------------------- | ---------------- | --------- |
| Access (GDPR Art. 15) | Export run rows + bug-report cards + subscription record into a single JSON bundle and email to subject.  | Kevin Armstrong  | 30 days   |
| Rectification (16)    | Update the corresponding Supabase / Trello / Stripe record in place.                                      | Kevin Armstrong  | 30 days   |
| Erasure (17)          | DELETE matching rows from `audit_runs`, archive + delete the Trello card, cancel + tombstone Stripe row.  | Kevin Armstrong  | 30 days   |
| Restriction (18)      | Set `restricted=true` on the relevant rows; suspends processing until lifted.                             | Kevin Armstrong  | 30 days   |
| Portability (20)      | Same as Access, served as JSON.                                                                           | Kevin Armstrong  | 30 days   |
| Objection (21)        | Stop further automated processing of the subject's data; cancel any active subscription on request.      | Kevin Armstrong  | 30 days   |

## Logging

Every request is logged under `compliance/dsar-log.md` (private repo,
not committed publicly) with: date received, subject identifier, right
exercised, action taken, completion date, evidence link. The log is
reviewed at the annual SOC 2 access-review cadence (see
`access-review-cadence.md`).

## References

- AICPA Trust Services Criteria — P5 (Privacy — disclosure and notification)
- GDPR Articles 15–22
- CCPA §1798.100–§1798.130

