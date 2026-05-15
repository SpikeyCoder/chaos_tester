---
title: CSP Hardening — object-src / base-uri / form-action / upgrade-insecure-requests
tsc: CC6, CC7
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-15
relates-to: app.py (_set_security_headers)
---

# CSP Hardening — website-auditor.io

## Background

`_set_security_headers` in `app.py` ships a strict Content-Security-Policy
on every Cloud Run response. As of 2026-05-14 the policy enumerated
`default-src`, `script-src`, `style-src-elem`, `style-src-attr`,
`img-src`, `connect-src`, `font-src`, and `frame-ancestors`. The
remaining "fetch directives + navigation directives + miscellaneous"
clauses were left to the `default-src 'self'` fallback.

Most fetch directives correctly inherit from `default-src`, but the
CSP3 specification carves out the following directives from the
fallback chain, meaning they must be set explicitly to be enforced:

- `object-src` — controls `<object>`, `<embed>`, `<applet>`. Without
  an explicit value the spec wording is implementation-defined and
  several older browsers (and a handful of headless engines used in
  ad-tech / scraping) fall back to a permissive default. Best practice
  is `object-src 'none'` to retire the legacy plugin XSS gadget
  surface.
- `base-uri` — controls the value of `<base href>`. An attacker who
  can inject a single tag (even one Trusted-Types-permitted attribute
  injection) can use `<base href="//attacker/">` to rewrite every
  relative URL on the page. Not covered by `default-src` (CSP3 §6.7).
- `form-action` — restricts where forms may POST/GET. CSP3 explicitly
  excludes this from `default-src` fallback (§6.7); the dashboard has
  no first-party forms today, so `'self'` is the right floor.
- `frame-src` — controls iframes. Today the dashboard renders no
  iframes; setting `'none'` documents that intent.
- `manifest-src` — controls the PWA manifest source.
- `worker-src` — controls Service / Shared / Dedicated workers; not
  covered by `default-src` (CSP3 §6.7).
- `upgrade-insecure-requests` — silently rewrites accidentally-authored
  `http://` subresources to `https://` so a single typo cannot become
  a mixed-content downgrade.

## Pen-test 2026-05-15 finding WA-2026-05-15-01

The Flask CSP relied on `default-src 'self'` to cover everything
unnamed. Adding the directives above closes the spec-carve-out and
brings parity with the kevinarmstrong.io worker CSP (`_worker.js`
`_CSP_BASE`) and the fundermatch.org Netlify `_headers` CSP.

## Control implemented (PR series 2026-05-15)

`_set_security_headers` now emits, in addition to the previous
directives:

- `object-src 'none'`
- `base-uri 'self'`
- `form-action 'self'`
- `frame-src 'none'`
- `worker-src 'self'`
- `manifest-src 'self'`
- `upgrade-insecure-requests`

`frame-ancestors 'none'` remains unchanged.

## Verification

1. Deploy the branch to Cloud Run; load `https://website-auditor.io`
   and confirm the response `Content-Security-Policy` header includes
   each of the directives above.
2. Open DevTools → Console — there should be zero CSP violation
   warnings on the first navigation (the dashboard does not use
   objects, iframes, base, forms, manifests, or workers today).
3. Run the existing static-style audit (`scripts/compute_style_hashes.py`)
   to confirm the `style-src-attr 'unsafe-hashes' …` list still
   matches every templated inline style — the hardening additions
   do not touch the style directives.

## References

- W3C — Content Security Policy Level 3, §6.7 "Effective directive"
  and §7 "Directives"
- OWASP Secure Headers Project — CSP cheat sheet
- CWE-1021 (Improper Restriction of Rendered UI Layers or Frames)
- AICPA TSC **CC6.6** and **CC7.1**
- Pen-test 2026-05-15 finding **WA-2026-05-15-01**
