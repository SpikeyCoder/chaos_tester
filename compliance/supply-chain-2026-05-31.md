---
title: Supply Chain Threat Review — 2026-05-31
tsc: CC3.1, CC3.2, CC7.1, CC7.2
owner: Kevin Armstrong
review-cadence: monthly
last-reviewed: 2026-05-31
---

# Supply Chain Threat Review — 2026-05-31

Re-checks our Python and frontend dependency graphs against active
supply chain campaigns reported by Socket.dev, StepSecurity, Snyk, Wiz,
GitGuardian, Tenable, and Microsoft Security in the 30 days leading up
to 2026-05-31.

## Campaigns reviewed

| Date | Campaign | Affected ecosystem(s) | Sample compromised packages | Source |
|------|----------|------------------------|------------------------------|--------|
| 2026-03 | Axios maintainer-account compromise | npm | `axios` (≥ 1.13.5 clean; ≥ 1.15.0 recommended) | CSA Singapore AD-2026-002 |
| 2026-04-22 | npm worm (Namastex Labs / CanisterWorm) | npm | misc agentic-AI packages | socket.dev |
| 2026-04-29 | TeamPCP SAP CAP compromise | npm | `@sap/cap-*` preinstall dropper | socket.dev |
| 2026-05-11 | Mini Shai-Hulud — TanStack + others | npm + PyPI | `@tanstack/*` (84 artifacts), `mistralai`, `@uipath/*`, `@antv/*`, Guardrails AI, OpenSearch | Snyk, Wiz, Microsoft, Tenable |
| 2026-05-19 | Microsoft `durabletask` PyPI hijack | PyPI | `durabletask` 1.4.1 / 1.4.2 / 1.4.3 (dropper for `rope.pyz`) | StepSecurity |
| 2026-05-22 | TrapDoor cross-ecosystem campaign | npm + PyPI + crates.io | 34+ packages, 384+ versions targeting crypto/DeFi/Solana/AI devs | TheHackerNews |
| 2026-05-29 | Bitwarden CLI 2026.4.0 compromise | npm (via CI/CD) | `@bitwarden/cli` 2026.4.0 | socket.dev |

## Exposure to website-auditor.io / chaos_tester

Cross-referenced against `requirements.txt`, `requirements.in`, root
`package.json` (no JS dependencies), and `frontend/` (static HTML only):

- `durabletask` (PyPI hijack): **not in `requirements.txt`.** Direct
  deps are flask, requests, beautifulsoup4, PyJWT, Flask-Limiter,
  gunicorn — none transitively pull `durabletask`.
- `mistralai`: **not in the dependency graph** (neither pip nor npm).
- `@tanstack/*`, `@uipath/*`, `@antv/*`, `@sap/cap-*`, `@bitwarden/cli`:
  no npm deps in this repo (root `package.json` has empty `scripts`
  and no `dependencies`; the static frontend lives in `frontend/`
  with no `package.json`).
- `axios`: **not in the dependency graph** (no npm deps at all).
- `idna` CVE-2026-45409 (DoS): already pinned to `idna==3.15` per the
  in-file note (see `requirements.txt`).

Direct exposure: **none** across all reviewed campaigns.

## Defensive controls re-verified

| Control | Status |
|---------|--------|
| `pip-audit -r requirements.txt`: 0 known vulnerabilities | Verified 2026-05-31 |
| `requirements.txt` fully pinned via `pip-compile` (transitive too) | Verified 2026-05-31 |
| `idna` pinned ≥ 3.15 (CVE-2026-45409 DoS) | Verified 2026-05-31 |
| Cloud Run image rebuilt from pinned base each deploy | Verified |
| `K_SERVICE`-gated fail-closed on missing `CHAOS_TESTER_SECRET_KEY` | In place (app.py:90) |
| SSRF defence on `/api/detect-business` and `_is_private_or_reserved` | In place (config.py + app.py) |

## Action items

1. Continue weekly Socket.dev / OSV / PyPI advisory review.
2. If a future release adds any of the compromised package families to
   `requirements.in`, hold the version below the compromise window and
   rotate any developer secrets that were accessible on the install host
   per the campaign-specific guidance.
3. Track Bitwarden CLI deprecation guidance — not in our path today but
   relevant if any future CI/CD step adds it.

## References

- [Snyk: TanStack npm Packages Compromised](https://snyk.io/blog/tanstack-npm-packages-compromised/)
- [Microsoft Security: Mini Shai-Hulud / @antv](https://www.microsoft.com/en-us/security/blog/2026/05/20/mini-shai-hulud-compromised-antv-npm-packages-enable-ci-cd-credential-theft/)
- [StepSecurity: Microsoft durabletask PyPI compromise](https://www.stepsecurity.io/blog/microsofts-durabletask-pypi-package-compromised-in-supply-chain-attack)
- [TheHackerNews: TrapDoor cross-ecosystem campaign](https://thehackernews.com/2026/05/trapdoor-supply-chain-attack-spreads.html)
- [Tenable: Mini Shai-Hulud FAQ (CVE-2026-45321)](https://www.tenable.com/blog/mini-shai-hulud-frequently-asked-questions)
