"""Smoke tests for WA-2026-05-12-01 (frame-ancestors) and WA-2026-05-12-02 (HSTS preload).

Loads app.py without actually starting Gunicorn and inspects the response headers
produced by _set_security_headers via a Flask test client.
"""
import pytest


def _client():
    from chaos_tester import app as mod
    mod.app.config["TESTING"] = True
    return mod.app.test_client()


def test_hsts_is_two_years_with_preload():
    resp = _client().get("/")
    hsts = resp.headers.get("Strict-Transport-Security", "")
    assert "max-age=63072000" in hsts, f"HSTS max-age should be 2y, got {hsts!r}"
    assert "includeSubDomains" in hsts
    assert "preload" in hsts


def test_csp_contains_frame_ancestors_none():
    resp = _client().get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in csp, f"frame-ancestors missing from CSP, got {csp!r}"
