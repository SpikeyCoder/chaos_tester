"""
Unit tests for chaos_tester.safe_http.SafeSession.

The SSRF guard is the difference between the runner being safe to point at
attacker-controlled URLs and the runner being a free probe of internal
services. These tests pin the contract: any prepared request whose hostname
resolves to a private / loopback / link-local / reserved / cloud-metadata
address must be refused before it goes on the wire.

Run: python -m pytest tests/test_safe_http.py
"""

from __future__ import annotations

import socket
from unittest import mock

import pytest
import requests

from chaos_tester.safe_http import SafeSession, SSRFBlockedError


def _patch_resolution(addresses):
    """Patch socket.getaddrinfo so the code under test resolves the
    test hostname to the supplied IPs."""
    def fake(hostname, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 0)) for a in addresses]
    return mock.patch("chaos_tester.config.socket.getaddrinfo", side_effect=fake)


@pytest.mark.parametrize("addr", [
    "127.0.0.1",
    "10.1.2.3",
    "192.168.0.1",
    "169.254.169.254",   # AWS / cloud metadata
    "::1",
])
def test_blocks_private_addresses(addr):
    s = SafeSession()
    with _patch_resolution([addr]):
        with pytest.raises(SSRFBlockedError):
            s.get("http://test.invalid/")


def test_blocks_metadata_hostname_without_resolution():
    s = SafeSession()
    # metadata.google.internal is in the static deny-list — should be
    # blocked even without DNS resolution.
    with pytest.raises(SSRFBlockedError):
        s.get("http://metadata.google.internal/computeMetadata/v1/")


def test_allows_public_address(monkeypatch):
    """Smoke test: a public-looking address bypasses the guard. Stubs
    the final requests.adapters.HTTPAdapter.send to avoid network."""
    s = SafeSession()
    captured = {}

    def fake_send(self, request, **kwargs):  # pylint: disable=unused-argument
        captured["url"] = request.url
        resp = requests.models.Response()
        resp.status_code = 200
        resp._content = b"ok"
        resp.url = request.url
        return resp

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)

    with _patch_resolution(["1.2.3.4"]):
        r = s.get("http://example.com/")
    assert r.status_code == 200
    assert captured["url"] == "http://example.com/"


# ── Pen-test 2026-06-10 (WA-2026-06-10-01 / -02) regression tests ─────────

@pytest.mark.parametrize("addr", [
    "100.100.100.200",   # Aliyun ECS IMDS (not is_private under stdlib)
    "100.64.0.1",        # CGNAT (RFC 6598)
    "100.127.255.254",   # CGNAT upper edge
])
def test_blocks_resolved_metadata_and_cgnat(addr):
    """Hostname that resolves to a cloud-IMDS literal or CGNAT must be
    refused even though Python stdlib does not flag the address as
    private or reserved.

    Pen-test 2026-06-10 finding WA-2026-06-10-01 (metadata by resolved IP)
    and WA-2026-06-10-02 (CGNAT coverage gap).
    """
    s = SafeSession()
    with _patch_resolution([addr]):
        with pytest.raises(SSRFBlockedError):
            s.get("http://attacker.example.com/")


def test_blocks_when_metadata_hostname_supplied_directly():
    """The literal cloud-IMDS hostname must be refused regardless of
    DNS resolution."""
    s = SafeSession()
    with pytest.raises(SSRFBlockedError):
        s.get("http://metadata.google.internal/")
