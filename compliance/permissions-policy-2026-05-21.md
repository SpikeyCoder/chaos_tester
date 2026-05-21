---
title: Permissions-Policy expansion (2026-05-21)
tsc: CC6.1, CC7.1
owner: Kevin Armstrong
last-reviewed: 2026-05-21
finding: WA-2026-05-21-01
relates-to: app.py
---

# Permissions-Policy expansion — 2026-05-21

## Context

The 2026-05-21 authorized pen-test flagged that the Flask
`@app.after_request` hook denied only four legacy features
(`camera`, `microphone`, `geolocation`, `interest-cohort`). Modern
browser surfaces (Topics API, Attribution Reporting, idle detection,
WebUSB, WebSerial, Web Bluetooth, Payment Request, WebAuthn passkey
assertion, Gamepad, WebXR) were left at the browser default.

## Change

`app.py` now emits a 37-directive deny-list. The directives that remain
enabled with `(self)` are:

- `fullscreen=(self)` — sample-report viewer fullscreen
- `picture-in-picture=(self)` — sample-report viewer PiP
- `web-share=(self)` — mobile share sheet

## Verification

After Cloud Run deploy:

```
curl -I https://website-auditor.io/ | grep -i permissions-policy
```

should return the expanded header. Mozilla Observatory scan: Permissions-Policy
item should flip to pass.

## References

- OWASP Secure Headers Project — Permissions-Policy
- W3C *Permissions Policy* spec
