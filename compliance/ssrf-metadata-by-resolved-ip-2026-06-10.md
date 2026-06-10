# SSRF guard hardening — WA-2026-06-10-01 / -02

**Date:** 2026-06-10
**Severity:** Medium (WA-2026-06-10-01), Low (WA-2026-06-10-02)
**Status:** Fixed in `sec/ssrf-block-by-resolved-ip-and-cgnat`

## Findings

### WA-2026-06-10-01 — Cloud-metadata blocklist bypassable by DNS

`config._is_private_or_reserved()` compared `BLOCKED_HOSTS` only
against the input hostname string. Python's `ipaddress.ip_address(
"100.100.100.200").is_private` returns `False`, so an attacker-
controlled hostname (or a DNS rebind) pointing at the Aliyun ECS IMDS
address (`100.100.100.200`) passed both the literal-host gate and the
private/reserved gate, reaching `SafeSession`.

### WA-2026-06-10-02 — CGNAT (100.64.0.0/10) not blocked

Python's `is_private` does not flag RFC 6598 CGNAT space, used by
ISP carrier-grade NAT and many VPN overlays (e.g. Tailscale's
`100.64/10`). A hostname resolving into CGNAT could be fetched
server-side.

## Fix

`config.py`:
- New constant `_BLOCKED_METADATA_IPS` — parsed `ip_address` objects
  for the four cloud-IMDS literals (`169.254.169.254`,
  `100.100.100.200`, `fd00:ec2::254`, `::ffff:169.254.169.254`).
- New constant `_BLOCKED_EXTRA_NETWORKS` — RFC 6598 `100.64.0.0/10`
  and NAT64 `64:ff9b::/96`, `64:ff9b:1::/48`.
- `_is_private_or_reserved()` now compares every **resolved** IP
  against both sets *after* the existing stdlib checks.

## Tests

`tests/test_safe_http.py`:
- New `test_blocks_resolved_metadata_and_cgnat` parametrised over
  `100.100.100.200`, `100.64.0.1`, `100.127.255.254`.
- New `test_blocks_when_metadata_hostname_supplied_directly` for the
  literal-hostname path.
- Result: 11/11 pass.

## TSC closure
- CC9 Risk Mitigation: closes the SSRF deny-list completeness gap.

## References
- CWE-918 Server-Side Request Forgery
- OWASP A10:2021 SSRF
- RFC 6598 (CGNAT), RFC 6052 (NAT64)
- Aliyun ECS IMDS docs
