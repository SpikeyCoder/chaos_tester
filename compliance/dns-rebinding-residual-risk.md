---
title: DNS Rebinding Residual Risk — SafeSession
tsc: CC3, CC9
owner: Kevin Armstrong
review-cadence: annually
last-reviewed: 2026-05-08
relates-to: safe_http.py, config._is_private_or_reserved
---

# DNS Rebinding Residual Risk — SafeSession

## Summary

`chaos_tester.safe_http.SafeSession` and `chaos_tester.config._is_private_or_reserved`
together protect every outbound HTTP request from Server-Side Request Forgery
(CWE-918, OWASP A10:2021). The hostname check fires on the seed URL,
on every redirect hop, and on every prepared request before it goes on the
wire.

A small theoretical attack window remains: between the hostname-to-IP
resolution performed by `_is_private_or_reserved` and the eventual TCP
connect performed by `urllib3` / `requests`, a malicious authoritative DNS
server could return a public address on the first lookup and an internal
address on the second (classic DNS rebinding).

## Risk acceptance

This residual risk is **accepted** at the current operating tier, on the
following basis:

1. The runner is invoked with attacker-supplied URLs only after a logged-in
   operator has approved the target, and the open dashboard endpoints
   (`/run`, `/api/detect-business`) are rate-limited and have a 5 MB body cap.
2. Cloud Run egress is restricted to public IP space by the platform-level
   network policy; the canonical cloud-metadata IPv4/IPv6 endpoints are
   already on the static blocklist in `config._is_private_or_reserved`.
3. The exploit requires the attacker to own a domain whose authoritative
   DNS server is willing to rebind on a sub-second TTL. Standard
   browser-targeted rebinding tooling (e.g. NCC Group's Singularity) is
   not effective against `requests` because Python re-resolves on every
   TCP connect rather than reusing the browser's host cache.

## Future work (not blocking)

The tightest available mitigation is to:

1. Resolve the hostname once (`socket.getaddrinfo`).
2. Validate the resolved address against `_is_private_or_reserved`'s rules.
3. Pin the connect to that exact IP via a custom `HTTPAdapter` so the
   second resolution cannot return a different address.

This is tracked as a low-priority hardening item and will be revisited if
the threat model changes (e.g. exposing the runner to fully untrusted
operators, or moving off Cloud Run's egress controls).

## References

- OWASP Server-Side Request Forgery Prevention Cheat Sheet
- CWE-918: Server-Side Request Forgery
- NIST SP 800-53 Rev. 5: SC-7, SI-10
