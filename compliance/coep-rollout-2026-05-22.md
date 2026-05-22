---
title: Cross-Origin-Embedder-Policy rollout — website-auditor.io
tsc: CC6.6, CC7.2
owner: Kevin Armstrong
review-cadence: as-needed
last-reviewed: 2026-05-22
applies-to: website-auditor.io (SpikeyCoder/chaos_tester)
finding-id: WA-2026-05-22-01
---

# COEP rollout — `credentialless`

## Why

Pen-test 2026-05-22 surfaced a parity gap with the
kevinarmstrong.io Cloudflare Worker (PR #34 / KA-2026-05-13-02):
that worker has set `Cross-Origin-Embedder-Policy: credentialless`
since 2026-05-13, but the chaos_tester Flask `_set_security_headers`
after_request handler set only `Cross-Origin-Opener-Policy` and
`Cross-Origin-Resource-Policy`. Without COEP, the HTML document
cannot enter a cross-origin isolated context, which leaves three
defense-in-depth properties on the table:

1. Spectre-class side channels remain reachable through shared-memory
   features (SharedArrayBuffer, high-resolution timers).
2. Accidental cross-origin subresources load silently instead of
   being surfaced as an explicit opt-in error (CORP / CORS).
3. The COOP boundary already in place advertises isolation intent
   that COEP is required to actually deliver.

## What

`_set_security_headers` now emits:

```
Cross-Origin-Embedder-Policy: credentialless
```

## Why `credentialless` and not `require-corp`

The dashboard currently loads exactly one cross-origin subresource
that lacks a `Cross-Origin-Resource-Policy` response header:
`https://website-auditor.goatcounter.com/count` (GoatCounter
analytics beacon). With `require-corp`, the browser would block
that request and analytics would silently stop. `credentialless`
solves the same problem by stripping ambient cookies on the
cross-origin hop instead of refusing the request outright, which:

- Preserves cross-origin isolation for the document.
- Keeps the GoatCounter pixel working (it does not depend on
  cookies).
- Surfaces any newly added cross-origin subresource that does
  depend on cookies as a console warning, so the regression is
  caught at deploy time rather than in production.

## Tightening path

Once every cross-origin dependency the dashboard loads advertises
a CORP header, this can be tightened to:

```
Cross-Origin-Embedder-Policy: require-corp
```

Monitor browser console for COEP warnings via the existing CSP
reporting endpoint pipeline (`/api/csp-report`) — `credentialless`
violations surface in browser DevTools but are not currently
auto-reported; revisit when the Reporting API ships a COEP report
type.

## Verification

After deploy, fetch any HTML route and confirm the header is
present:

```
curl -sI https://website-auditor.io/ | grep -i 'cross-origin-embedder-policy'
# expected: Cross-Origin-Embedder-Policy: credentialless
```

## References

- [HTML: Cross-origin isolation](https://html.spec.whatwg.org/multipage/origin.html#cross-origin-isolated)
- [MDN: Cross-Origin-Embedder-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy)
- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- kevinarmstrong.io rollout: `compliance/coep-rollout-2026-05-13.md`
