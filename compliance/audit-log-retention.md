# Audit Log Retention Policy — website-auditor.io

**Owner:** Kevin Armstrong (kevinmarmstrong1990@gmail.com)
**Last reviewed:** 2026-05-11
**Review cadence:** Quarterly
**Applies to:** Armstrong HoldCo LLC / website-auditor.io (chaos_tester)

## Purpose

Documents what audit and operational log data is collected across the
website-auditor.io stack, how long it is retained, who has access, and
how it is reviewed. Satisfies SOC 2 Trust Services Criterion **CC4
(Monitoring Activities)** and provides an audit trail for incident
response (see `compliance/incident-response.md`).

## Log sources, retention, and access

| Source                              | What it records                                          | Retention            | Access                                |
|-------------------------------------|----------------------------------------------------------|----------------------|---------------------------------------|
| Google Cloud Run request logs       | HTTP request metadata for the Flask app                  | 30 days (default)    | GCP project owner                     |
| Google Cloud Run stderr/stdout      | App logger output (rate-limit hits, SSRF rejections, errors) | 30 days (default) | GCP project owner                     |
| GitHub Pages logs                   | Static dashboard requests                                | n/a (none)           | n/a                                   |
| Supabase REST + Postgres logs       | Report storage queries, RLS denials                      | 7 days (free tier)   | Supabase dashboard owner              |
| Cloudflare (DNS / WAF)              | DNS resolutions, WAF events                              | 30 days              | Cloudflare account owner              |
| Trello webhook (bug-report destination) | Created cards, attachments                            | Indefinite (Trello)  | Trello workspace owner                |
| GitHub audit log                    | Repo access, branch-protection changes, secret-scan      | 90 days (free tier)  | GitHub account owner                  |
| Dependabot security advisories      | Vulnerability alerts                                     | Indefinite           | Repo security tab                     |

Retention is bounded by the **most-restrictive** of provider-tier limits
and this policy. Where the provider stores data longer than required
(Trello), the policy does not extend retention — it only documents the
practical floor.

## In-app application logs

The Flask app logs via Python `logging`. The following events are emitted
at INFO+ and visible in Cloud Run logs:

* SSRF rejection (host failed `_is_private_or_reserved`).
* Rate-limit exceeded (`flask-limiter` 429s).
* CSRF gate trip (`X-Requested-With` missing).
* Subscription gate denial on `/api/ai-query`.
* Trello card creation failure.
* Screenshot validation rejection (size / non-PNG bytes).
* `wa_auth` token audience mismatch (when `WA_REQUIRED_AUDIENCE` is set).
* Bug-report submissions (anonymised — no PII beyond what the reporter
  voluntarily includes in the description).

PII handling: per `compliance/data-classification.md`, no end-user PII
is intentionally logged. IP addresses appear only in upstream Cloud Run
request logs, not in application logs.

## Long-term audit trail

For events that must outlive the provider window (incidents, access
reviews, configuration changes, vulnerability disclosures), the canonical
store is the relevant Markdown file under `compliance/`, which lives in
git and is retained for the life of the repository.

Specifically:

* **Access reviews** — `compliance/access-review-cadence.md`.
* **Security incidents** — `compliance/incident-response.md` plus a
  per-incident `SECURITY-INCIDENT-<date>.md` file at repo root once an
  incident is declared.
* **Vendor changes** — `compliance/vendor-inventory.md`.
* **CSP / inline-style audits** — `compliance/inline-style-audit-*.md`.
* **Pen-test reports** — `Armstrong_HoldCo_Pentest_Report_<date>.docx`
  in the shared kevinarmstrong.io repo, retained indefinitely.

## Review cadence

Once per quarter the owner:

1. Confirms Cloud Run log retention is at its default 30 days (no
   accidental disablement) by spot-checking the Logs Explorer.
2. Verifies Supabase logging is active by sampling RLS-deny events.
3. Reviews Dependabot alerts and the GitHub security tab.
4. Records the outcome in `compliance/access-review-cadence.md`.

## Incident retention extension

When an incident is declared, the owner downloads the relevant log
ranges from Cloud Run, Supabase, and Cloudflare to encrypted local
storage within 24 hours, since provider windows are short. The
downloaded set is held for the duration of the incident plus three
years.

## References

* AICPA Trust Services Criteria 2017 (rev. 2022) — CC4.1, CC4.2
* NIST SP 800-53 Rev. 5 — AU-11 (Audit Record Retention)
* CIS Controls v8 — Control 8 (Audit Log Management)
