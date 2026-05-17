---
title: Branch Protection & Code Review Policy
tsc: CC5.1, CC5.2, CC8.1
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-17
applies-to: website-auditor.io (SpikeyCoder/chaos_tester)
finding-id: WA-2026-05-17-02
---

# Branch Protection & Code Review Policy — website-auditor.io

This policy is the formal artefact backing AICPA TSC **CC5.1 / CC5.2**
("the entity selects and develops control activities" / "the entity
deploys control activities through policies and procedures") and
**CC8.1** ("the entity authorizes, designs, develops or acquires,
configures, documents, tests, approves, and implements changes to
infrastructure, data, software, and procedures").

It exists so an auditor can map "change management is gated by review
and required checks" to a concrete artefact rather than a paragraph in
the README, and so a future repo administrator has the exact GitHub
settings written down.

## 1. Protected branch

- **Repository:** `SpikeyCoder/chaos_tester`
- **Branch:** `main`
- **Production deployment trigger:** push to `main` → GitHub Actions
  workflow `.github/workflows/deploy-cloud-run.yml` builds the Docker
  image and deploys to Google Cloud Run.

## 2. Required GitHub branch-protection settings

| Setting | Value | Why |
|---|---|---|
| Require a pull request before merging | ON | No direct pushes to `main`; every change is reviewable |
| Required approvals | 1 | Single-owner repo; the owner is also CODEOWNERS for every path (see `.github/CODEOWNERS`) |
| Dismiss stale approvals on new commits | ON | New commits to a reviewed PR must be re-reviewed |
| Require review from Code Owners | ON | Enforces `.github/CODEOWNERS` on security-sensitive paths (`/app.py`, `/safe_http.py`, `/wa_auth.py`, `/modules/security.py`, `/modules/auth.py`, `/Dockerfile`, `/requirements.txt`, `/SECURITY.md`, `/compliance/`, `/.github/`) |
| Require status checks to pass before merging | ON | CI must be green before merge |
| Required status checks | `pr-validation` (see `.github/workflows/pr-validation.yml`) | Runs `python -m pytest tests/` and a syntax check; blocks merges that break the rate-limit / SSRF / wa_auth suite |
| Require branches to be up to date before merging | ON | Forces rebase/merge against latest `main` so CI runs against the post-merge tree |
| Require conversation resolution before merging | ON | No outstanding review comments at merge time |
| Require signed commits | OFF (recommended P2) | Single-owner; signed commits planned once a second maintainer joins (see CC1 review notes) |
| Require linear history | ON | Merge commits or rebase only; no merge-commit-on-merge-commit chains that complicate `git bisect` |
| Do not allow bypassing the above settings | ON | The repo administrator cannot push directly to `main` even in an emergency; emergency procedure documented below |
| Restrict who can push to matching branches | Empty (owner-only via PR) | No service accounts can push to `main` |
| Allow force pushes | OFF | `main` history is append-only |
| Allow deletions | OFF | `main` cannot be deleted |

## 3. Required status checks — current set

- `pr-validation` — runs on every PR (see `.github/workflows/pr-validation.yml`):
  - `python -m pytest tests/` — full suite, including `test_rate_limit.py`,
    `test_safe_http.py`, `test_wa_auth_audience.py`,
    `test_security_headers_wa_2026_05_12.py`, `test_security_txt.py`,
    `test_business_identifier_ip_ranking.py`.
  - `python -m py_compile $(git ls-files '*.py')` — syntax gate.

Future status checks (P2):

- `pip-audit -r requirements.txt --strict` once `pip-audit` is wired
  into the workflow (CC7).
- `bandit -r . -ll` once a clean baseline is established (CC7).

## 4. Code Owners — `.github/CODEOWNERS`

Code Owners are auto-requested on every PR. The current owner list
matches `.github/CODEOWNERS`:

```text
*                              @SpikeyCoder
/SECURITY.md                   @SpikeyCoder
/compliance/                   @SpikeyCoder
/.github/                      @SpikeyCoder
/safe_http.py                  @SpikeyCoder
/wa_auth.py                    @SpikeyCoder
/app.py                        @SpikeyCoder
/modules/auth.py               @SpikeyCoder
/modules/security.py           @SpikeyCoder
/Dockerfile                    @SpikeyCoder
/requirements.txt              @SpikeyCoder
```

Adding any new owner requires a CC1 review (control environment) — the
new owner must (a) have MFA enforced on their GitHub account and (b) be
listed in the vendor inventory access-review.

## 5. Emergency-change procedure

If a SEV-1 incident (see `compliance/incident-response.md`) requires a
bypass:

1. Owner opens a "break-glass" PR titled
   `EMERGENCY: <short description> [break-glass]`.
2. CI still runs; if CI is failing because of the incident itself, the
   failing check is annotated in the PR body with the incident ticket.
3. The owner uses the GitHub "Merge without waiting for requirements"
   option (visible only to administrators when "Do not allow bypassing"
   is OFF for administrators — this remains the documented escape
   hatch; otherwise revert by force-merge of a pre-approved hotfix
   branch).
4. Within 24 hours of the break-glass merge, the owner files a
   post-incident review entry in `compliance/risk-register.md` under
   "post-merge attestations" and updates this policy if a process gap
   contributed to the bypass.

The break-glass procedure has been used **0 times** since this policy
was first ratified.

## 6. Verification

Branch-protection settings are verified at the start of every quarterly
SOC 2 readiness review:

1. Visit
   `https://github.com/SpikeyCoder/chaos_tester/settings/branches`.
2. Confirm the `main` rule matches §2 row-by-row.
3. Screenshot the settings page and attach to the quarterly review note
   in `compliance/access-review-cadence.md`.

Next scheduled verification: **2026-08-17** (90 days from
`last-reviewed`).

## 7. References

- AICPA Trust Services Criteria (2017, revised 2022) — CC5, CC8.
- GitHub Docs — *Managing a branch protection rule*
  (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).
- NIST SP 800-218 SSDF — PO.3.2 (separation of duties via PR review),
  PW.7.1 (review changes before merge).
- OWASP SAMM — Implementation : Secure Build — Build Process.
