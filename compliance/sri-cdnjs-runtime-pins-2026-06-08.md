---
title: SRI pins for runtime-loaded cdnjs.cloudflare.com scripts
finding-id: WA-2026-06-08-01
tsc: CC6.6, CC6.7, CC7.1
date: 2026-06-08
owner: Kevin Armstrong
status: closed
---

# SRI pins for runtime-loaded `cdnjs.cloudflare.com` scripts

## Finding (closes pen-test 2026-06-06 WA-2026-06-06-01)

Three runtime-loaded scripts from `cdnjs.cloudflare.com` were injected
into the page without Subresource Integrity (SRI) pins:

- `jspdf 2.5.1` (`static/js/report-page.js`) — PDF export on report page.
- `jspdf-autotable 3.8.2` (`static/js/report-page.js`) — table plugin for jsPDF.
- `html2canvas 1.4.1` (`static/js/bug-report.js`) — DOM-to-canvas capture for bug-report screenshots.

CSP allow-lists `cdnjs.cloudflare.com` under `script-src`, which is
required for these dynamic injections to load. Without SRI, a
compromise of cdnjs (or of the specific package version) would result
in arbitrary JS execution in page context (CWE-829 — Inclusion of
Functionality from Untrusted Control Sphere). This was tracked as an
Informational follow-up by the 2026-06-06 pen-test (WA-2026-06-06-01).

## Resolution

Each `<script>` injection now includes:

- `integrity="sha384-…"` — locks the bytes to the audited version.
- `crossOrigin="anonymous"` — required by browsers to enforce SRI on
  cross-origin scripts and to omit cookies/credentials on the fetch.
- `referrerPolicy="no-referrer"` — minimises information leak to the
  CDN about which internal report page triggered the fetch.

SHA-384 hashes were computed locally against the exact CDN-served
bytes at audit time:

```
jspdf 2.5.1                 sha384-JcnsjUPPylna1s1fvi1u12X5qjY5OL56iySh75FdtrwhO/SWXgMjoVqcKyIIWOLk
jspdf-autotable 3.8.2       sha384-fCAW/rDWORTbQXSiB7mOg0QtQ5c+r0f544y6XoKjuVva0nMBlCpNUjiFeG5iMdS3
html2canvas 1.4.1           sha384-ZZ1pncU3bQe8y31yfZdMFdSpttDoPmOZg2wguVK9almUodir1PghgT0eY7Mrty8H
```

Hash recomputation procedure (re-run before any version bump):

```sh
for f in jspdf-2.5.1.js jspdf-autotable-3.8.2.js html2canvas-1.4.1.js; do
  echo -n "$f: sha384-"; openssl dgst -sha384 -binary "$f" | openssl base64 -A; echo
done
```

## Verification

1. In DevTools, load `/report/<run_id>` and click "Download PDF" — the
   network panel shows the `jspdf.umd.min.js` and
   `jspdf.plugin.autotable.min.js` responses fetched cross-origin with
   the `integrity` attribute echoed and status 200; tampering with the
   bytes (e.g. via a local proxy) causes the browser to refuse
   execution.
2. Likewise for the bug-report widget — clicking the bug button
   triggers `html2canvas.min.js` fetch and validation.
3. `/api/csp-report` (Cloud Logging) shows no new `script-src`
   violations after deploy.

## References

- W3C Subresource Integrity 1.0 specification.
- CWE-829 — Inclusion of Functionality from Untrusted Control Sphere.
- OWASP A06:2021 — Vulnerable and Outdated Components.
- AICPA Trust Services Criteria CC6.6, CC6.7, CC7.1.
