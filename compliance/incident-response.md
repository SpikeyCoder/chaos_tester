---
title: Incident Response Runbook
tsc: CC4, CC7
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-04
---

# Incident Response — website-auditor.io

## Detection sources
- Cloud Run logs / error metrics
- GitHub secret scanning + Dependabot security advisories
- External: emails to kevinmarmstrong1990@gmail.com

## Severity matrix
| Sev | Definition | Response time |
|---|---|---|
| SEV-1 | Active customer-impacting outage, confirmed data exposure, or active exploitation | < 1 hour |
| SEV-2 | Confirmed vulnerability, no exploitation observed, or partial outage | < 24 hours |
| SEV-3 | Misconfiguration, low-risk vulnerability, or hygiene gap | < 7 days |

## Workflow
1. Acknowledge in writing within SLA.
2. Triage — confirm reproducibility, scope, severity.
3. Contain — disable the vulnerable code path (Cloud Run revision rollback,
   Cloudflare WAF rule, Trello app revoke, Perplexity key rotate).
4. Eradicate — fix on `security/*` branch → merge → redeploy.
5. Recover — verify production healthy.
6. Notify — affected users / processors per privacy policy and law.
7. Postmortem — within 7 days for SEV-1/2 in compliance/postmortems/.

## Roles
- Incident Commander: Kevin Armstrong (single-owner org)

## Tabletop cadence
Annually, with one unscheduled SEV-2 simulation.
