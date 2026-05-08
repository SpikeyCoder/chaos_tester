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
