---
title: Privacy Controls — website-auditor.io
tsc: P1, P2, P3, P4, P5, P6, P7, P8
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-27
opened-from: pen-test 2026-05-27 finding WA-2026-05-27-01
---

# Privacy Controls (website-auditor.io)

This document describes how website-auditor.io implements the AICPA
Trust Services Criteria for **Privacy (P1–P8)** for the public scanning
UI at https://website-auditor.io and the gated API at
https://api.website-auditor.io. It is the policy-level counterpart to
the public privacy notice (rendered from `templates/privacy.html`),
the public security disclosure at `/.well-known/security.txt`, the
DSAR runbook at `compliance/dsar-runbook.md`, the retention floors at
`compliance/retention-and-deletion.md`, and the audit-log policy at
`compliance/audit-log-retention.md`.

It was added to bring website-auditor.io to parity with the existing
privacy-controls policies at `kevinarmstrong.io` and `fundermatch.org`,
closing pen-test 2026-05-27 finding WA-2026-05-27-01.

## P1 — Notice and Communication of Privacy Commitments

- Public privacy notice is rendered from `templates/privacy.html` and
  linked from the site footer. It describes what is collected, how it
  is used, third-party processors (Supabase, GoatCounter, Perplexity,
  Trello), retention floors, and how to exercise DSAR rights.
- The notice is versioned in git; every material change is committed
  and the rendered "Last updated" line is bumped.
- Material processing changes additionally trigger an in-app
  notification (rendered via the homepage status bar) for 30 days
  after deploy.
- `/.well-known/security.txt` advertises a security contact for
  vulnerability disclosure (CC2.3 evidence).

## P2 — Choice and Consent

- Anonymous scanning of a public URL is the default; the visitor
  supplies the target URL and optionally a business location, and the
  scan output is rendered without an account.
- The subscription-gated `/api/ai-query` endpoint requires an account
  at `api.website-auditor.io` (Google OAuth or Supabase magic link)
  and an active or trialing subscription. The visitor explicitly
  consents to processing by signing in.
- The bug-report widget (`/api/bug-report`) is opt-in — clicking
  "Report a bug" surfaces a modal that captures the user's typed
  description and (with explicit consent each time) a viewport
  screenshot.
- The site uses **GoatCounter** for first-party, cookieless analytics
  — no consent banner is required because no PII, cross-site
  tracking, or persistent identifiers are stored.

## P3 — Collection

The site practises minimum-necessary collection:

| Category | What is collected | Lawful basis | Where it lives |
| --- | --- | --- | --- |
| Scan target | URL string (and optional city for AI visibility) | Explicit user submission | Run history (`run_history.jsonl`) |
| Subscription identity | `api_users.id`, email, OAuth `sub` | Contract performance | Supabase `api_users` table |
| Subscription status | Stripe subscription state (active/trialing/cancelled) | Contract performance | Supabase `subscriptions` table |
| Bug report | Free-text description, optional viewport screenshot, runtime context (URL, user-agent, viewport size, last 5 console errors) | Explicit consent at each submission | Trello card via the configured `TRELLO_LIST_ID` |
| Access log | Caller IP, geo (from `X-Appengine-CityLatLong`), user-agent | Legitimate interest (abuse defence and rate-limiting) | Cloud Run access log (24 h hot, 30 d cold) |

The wa_auth cookie carries only the signed `api_users.id` and an `exp`
claim — no email or profile data.

## P4 — Use, Retention, and Disposal

- **Retention floors** are codified in `compliance/retention-and-deletion.md`:
  - Run history: 90 days hot, then aggregated metrics only.
  - Bug-report screenshots: never persisted server-side outside the
    Trello card; the card is auto-archived after 180 days.
  - Access log: 30 days, then deleted.
- **Disposal** is enforced by a daily Cloud Run job that prunes
  expired records; see the daily access-log rotation script and the
  Trello list automation.
- Use is limited to (a) returning the scan report to the requester,
  (b) showing aggregate (non-PII) usage statistics on the homepage,
  and (c) abuse defence. No data is sold or shared with marketing
  processors.

## P5 — Access (DSAR)

- DSARs are handled per `compliance/dsar-runbook.md`. Requests are
  fulfilled within 30 days and acknowledged within 5 business days.
- For subscription holders, the request is satisfied from the
  Supabase `api_users` and `subscriptions` tables plus any open
  Trello bug reports they submitted.
- For anonymous visitors, the only realistically identifying data is
  the IP/UA pair in the access log, which is purged on the 30-day
  cadence above; we acknowledge that the access-log payload does not
  carry an identity link.

## P6 — Disclosure to Third Parties

| Processor | Purpose | DPA in place |
| --- | --- | --- |
| Supabase | Identity, subscription state, run-history persistence | Yes — `compliance/vendor-inventory.md` |
| Stripe | Subscription billing (chaos_tester does not see card data) | Yes — `compliance/vendor-inventory.md` |
| GoatCounter (self-hosted) | First-party cookieless analytics | N/A (self-hosted) |
| Perplexity AI | Custom AI visibility queries (subscription-gated) | Yes — `compliance/vendor-inventory.md` |
| Trello | Bug report triage | Yes — `compliance/vendor-inventory.md` |
| Google Cloud Run | Hosting | Yes (Google Workspace DPA) |

No data is disclosed for marketing, training, or any other purpose
outside the table above.

## P7 — Quality

- Subscription data is the system of record from Stripe webhook
  `customer.subscription.*` events; the local `subscriptions` table
  is overwritten on each event so the local copy cannot drift.
- Scan output is derived from the live target URL at scan time and
  is never edited after the fact; if a finding is wrong the run is
  re-executed rather than mutated.
- Users can correct or delete their account via the admin portal at
  `api.website-auditor.io/admin_portal/` (drives P5 + P7).

## P8 — Monitoring and Enforcement

- Privacy complaints follow the disclosure path in
  `compliance/incident-response.md`. Material privacy incidents are
  tracked in the same risk register as security incidents.
- Annual review of this document and of `compliance/dsar-runbook.md`,
  `compliance/retention-and-deletion.md`, and
  `compliance/vendor-inventory.md` is scheduled (see
  `compliance/access-review-cadence.md`).
- Quarterly access reviews verify that only the documented engineering
  and ops accounts have admin access to the Supabase project and the
  Cloud Run service.

## Change history

- 2026-05-27 — Initial version. Created in response to pen-test
  finding WA-2026-05-27-01 (parity gap: kevinarmstrong.io and
  fundermatch.org both ship a `privacy-controls.md`; website-auditor.io
  did not).
