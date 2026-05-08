"""
Contract test for the RFC 9116 security.txt endpoint.

Asserts that:
  - /.well-known/security.txt is reachable
  - response type is text/plain
  - required disclosure fields are present
  - route content matches the static source-of-truth file
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone


PROJECT_PARENT = Path(__file__).resolve().parents[2]
if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))

os.environ.setdefault("CHAOS_TESTER_SECRET_KEY", "test-key-32-bytes-test-key-32-bytes")

from chaos_tester.app import BASE_DIR, app


def test_security_txt_contract():
    client = app.test_client()
    response = client.get("/.well-known/security.txt")

    assert response.status_code == 200
    assert response.headers.get("Content-Type", "").startswith("text/plain")

    body = response.get_data(as_text=True)
    for required_line in (
        "Contact: mailto:",
        "Expires:",
        "Preferred-Languages:",
        "Canonical:",
        "Policy:",
    ):
        assert required_line in body

    static_path = BASE_DIR / "static" / ".well-known" / "security.txt"
    assert body.strip() == static_path.read_text(encoding="utf-8").strip()


def test_security_txt_expires_window():
    """Track RFC expiry so we refresh proactively before it lapses.

    Guardrails:
      - `Expires` must be in the future by at least 30 days.
      - `Expires` must not exceed one year from now (RFC 9116 guidance).
    """
    content = (BASE_DIR / "static" / ".well-known" / "security.txt").read_text(encoding="utf-8")
    expires_line = next(
        (line for line in content.splitlines() if line.startswith("Expires: ")),
        "",
    )
    assert expires_line, "Missing Expires line in security.txt"

    expires_str = expires_line.split("Expires: ", 1)[1].strip()
    expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    # Trip early enough to refresh before expiry instead of after breakage.
    assert expires_at >= now + timedelta(days=30), (
        f"security.txt Expires is too close ({expires_str}); refresh it now."
    )
    assert expires_at <= now + timedelta(days=366), (
        f"security.txt Expires exceeds RFC one-year window ({expires_str})."
    )
