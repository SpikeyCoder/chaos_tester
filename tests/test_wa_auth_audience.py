"""Tests for the optional audience-pinning behavior on wa_auth JWTs.

Pen-test 2026-05-11 added WA_REQUIRED_AUDIENCE so operators can lock
wa_auth tokens to a specific ``aud`` claim. These tests confirm:

  1. With WA_REQUIRED_AUDIENCE unset, legacy tokens (no aud claim)
     decode successfully — backward compatibility preserved.
  2. With WA_REQUIRED_AUDIENCE set, tokens minted with the matching
     ``aud`` decode successfully.
  3. With WA_REQUIRED_AUDIENCE set, tokens minted with a different
     ``aud`` are rejected (return None).
  4. Expired tokens are rejected regardless of audience.
"""
from __future__ import annotations

import importlib
import os
import time

import jwt
import pytest


SECRET = "test-secret-do-not-use-in-prod"


@pytest.fixture
def wa_auth_module(monkeypatch):
    monkeypatch.setenv("WA_SHARED_SECRET", SECRET)
    from chaos_tester import wa_auth as mod  # type: ignore
    importlib.reload(mod)
    return mod


def _mint(payload: dict) -> str:
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_no_audience_required_accepts_token_without_aud(wa_auth_module, monkeypatch):
    monkeypatch.delenv("WA_REQUIRED_AUDIENCE", raising=False)
    token = _mint({"sub": "user-1", "exp": int(time.time()) + 3600})
    assert wa_auth_module._decode_token(token) is not None


def test_required_audience_accepts_matching_aud(wa_auth_module, monkeypatch):
    monkeypatch.setenv("WA_REQUIRED_AUDIENCE", "chaos-tester")
    importlib.reload(wa_auth_module)
    token = _mint({"sub": "user-1", "aud": "chaos-tester", "exp": int(time.time()) + 3600})
    assert wa_auth_module._decode_token(token) is not None


def test_required_audience_rejects_mismatched_aud(wa_auth_module, monkeypatch):
    monkeypatch.setenv("WA_REQUIRED_AUDIENCE", "chaos-tester")
    importlib.reload(wa_auth_module)
    token = _mint({"sub": "user-1", "aud": "admin-portal", "exp": int(time.time()) + 3600})
    assert wa_auth_module._decode_token(token) is None


def test_required_audience_rejects_missing_aud(wa_auth_module, monkeypatch):
    monkeypatch.setenv("WA_REQUIRED_AUDIENCE", "chaos-tester")
    importlib.reload(wa_auth_module)
    token = _mint({"sub": "user-1", "exp": int(time.time()) + 3600})
    assert wa_auth_module._decode_token(token) is None


def test_expired_token_rejected(wa_auth_module, monkeypatch):
    monkeypatch.delenv("WA_REQUIRED_AUDIENCE", raising=False)
    token = _mint({"sub": "user-1", "exp": int(time.time()) - 60})
    assert wa_auth_module._decode_token(token) is None
