# Contributing

This repository powers [website-auditor.io](https://website-auditor.io). It is
a Flask app deployed on Google Cloud Run. The codebase is closed-source but
follows the same workflow as other Armstrong HoldCo repos.

## Ground rules

- All changes land on `main` through a pull request — direct pushes are
  blocked by branch protection.
- Every PR must pass `pr-validation.yml` (lint + tests + audit) and be
  reviewed by the project maintainer (@SpikeyCoder).
- Security-sensitive changes (SSRF guard, CSP, rate-limits, auth, JWT,
  CORS) must reference the relevant pen-test finding ID and update the
  appropriate doc in `compliance/`.

## Branch naming

| Prefix       | Use for                                  |
|--------------|------------------------------------------|
| `feature/`   | new functionality                        |
| `fix/`       | non-security bug fixes                   |
| `security/`  | security fixes / hardening               |
| `compliance/`| SOC 2 / policy docs                      |
| `chore/`     | dependency bumps, formatting             |

## Reporting a vulnerability

Use the private channel described in [SECURITY.md](./SECURITY.md). Do not file
a public issue for security-sensitive findings.

## Local development

```bash
pip install -r requirements.txt
flask --app app run --debug --port 8080
```

## Code review checklist

- [ ] Tests added or updated where applicable.
- [ ] No secrets committed — environment variables only.
- [ ] CSP / security headers unchanged unless intentional.
- [ ] Outbound HTTP for user-supplied URLs goes through `SafeSession`.
- [ ] Rate-limit decorators present on any new endpoint that hits a paid API.
