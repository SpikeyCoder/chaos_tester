"""
Smoke test for Flask-Limiter wiring on the open POST endpoints.

Asserts that:
  - the 4th /run POST inside one minute returns 429
  - /api/bug-report becomes 429 after 5 calls/min
  - /api/detect-business becomes 429 after 10 calls/min

Stubs out the heavy work (test runner, Trello, SafeSession) so the test
runs offline and finishes in <5 s.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

# Force the limiter to use in-memory storage for the test.
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")
os.environ.setdefault("CHAOS_TESTER_SECRET_KEY", "test-key-32-bytes-test-key-32-bytes")


class RateLimitSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import flask_limiter  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("flask_limiter not installed in this environment")
        from chaos_tester.app import app, limiter
        app.config["TESTING"] = True
        # Limiter must be enabled in TESTING; flask-limiter respects RATELIMIT_ENABLED.
        app.config["RATELIMIT_ENABLED"] = True
        limiter.reset()
        cls.app = app
        cls.client = app.test_client()
        cls.limiter = limiter

    def setUp(self):
        # Reset between tests so per-IP buckets don't leak.
        self.limiter.reset()

    def _post(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )

    def test_run_limited_to_3_per_min(self):
        # Stub the runner so /run doesn't try to crawl.
        with patch("chaos_tester.app.threading.Thread"):
            statuses = [self._post("/run", {"base_url": "https://example.com"}).status_code for _ in range(4)]
        # First 3 should be accepted (202 or possibly 409 if state lingers); the 4th must be 429.
        self.assertEqual(statuses[3], 429, f"expected 429 on 4th call, got {statuses}")

    def test_bug_report_limited(self):
        with patch("chaos_tester.app.os.getenv", return_value=""):
            # When env is missing, bug-report returns 500 — but the limit check fires first
            # so we still see 429 after 5 calls.
            statuses = [self._post("/api/bug-report", {"description": "x"}).status_code for _ in range(6)]
        self.assertEqual(statuses[5], 429, f"expected 429 on 6th call, got {statuses}")

    def test_detect_business_limited(self):
        with patch("chaos_tester.modules.business_identifier.BusinessIdentifier"):
            statuses = [self._post("/api/detect-business", {"url": "https://example.com"}).status_code for _ in range(11)]
        self.assertEqual(statuses[10], 429, f"expected 429 on 11th call, got {statuses}")


if __name__ == "__main__":
    unittest.main()
