"""
SSRF-aware requests.Session.

`config.ChaosConfig.validate()` already rejects a base_url that resolves
to a private/loopback/link-local/reserved/cloud-metadata IP. But that
check runs *once*, at the start of a run — subsequent crawler-discovered
links and HTTP redirects aren't re-validated, so a malicious redirect or
DNS rebinding could pivot the runner onto an internal endpoint.

`SafeSession.send()` runs the same hostname check on every prepared
request before it goes on the wire, including the targets of redirects,
so the SSRF guard now applies to the entire run instead of just the seed.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

from .config import _is_private_or_reserved

logger = logging.getLogger("chaos_tester.safe_http")


class SSRFBlockedError(requests.RequestException):
    """Raised when an outbound request targets a private / reserved address."""


class SafeSession(requests.Session):
    """
    A drop-in `requests.Session` that vetoes outbound requests whose
    hostname resolves to a private, loopback, link-local, reserved, or
    cloud-metadata address.

    The check fires both for the initial request and for any redirect
    target — `requests.Session.resolve_redirects()` calls `self.send()`
    again for each hop, so this same `send()` will gate every redirect.
    """

    def send(self, request, **kwargs):  # type: ignore[override]
        hostname = urlparse(request.url).hostname or ""
        if hostname and _is_private_or_reserved(hostname):
            logger.warning(
                "SSRF guard blocked outbound request to %s (host=%s)",
                request.url,
                hostname,
            )
            raise SSRFBlockedError(
                f"SSRF guard: refusing to fetch {request.url!r} — "
                f"hostname {hostname!r} resolves to a private or reserved address."
            )
        return super().send(request, **kwargs)
