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
        import chaos_tester.app as app_module
        from chaos_tester.app import app, limiter
        app.config["TESTING"] = True
        app.config["RATELIMIT_ENABLED"] = True
        limiter.reset()
        cls.app_module = app_module
        cls.app = app
        cls.client = app.test_client()
        cls.limiter = limiter

    def setUp(self):
        # Reset between tests so per-IP buckets and in-memory run state do not leak.
        self.limiter.reset()
        with self.app_module._lock:
            self.app_module._current_status = "idle"
            self.app_module._current_run = None
            self.app_module._progress.clear()
            self.app_module._highest_pct = 0

    def _post(self, path, payload):
        return self.client.post(
            path,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )

    def test_run_limited_to_3_per_min(self):
        # Stub thread startup and force idle between calls so business-state
        # guards don't mask the limiter behavior.
        responses = []
        with patch("chaos_tester.app._run_tests", return_value=None):
            for _ in range(4):
                responses.append(self._post("/run", {"base_url": "https://example.com"}))
                with self.app_module._lock:
                    self.app_module._current_status = "idle"

        statuses = [r.status_code for r in responses]
        self.assertEqual(statuses[:3], [202, 202, 202], f"expected first 3 calls accepted, got {statuses}")
        self.assertEqual(statuses[3], 429, f"expected 429 on 4th call, got {statuses}")
        self.assertTrue(responses[3].headers.get("Retry-After", "").isdigit())
        self.assertGreaterEqual(responses[3].get_json()["retry_after"], 1)

    def test_bug_report_limited(self):
        with patch("chaos_tester.app.os.getenv", return_value=""):
            statuses = [self._post("/api/bug-report", {"description": "x"}).status_code for _ in range(6)]
        self.assertEqual(statuses[:5], [500, 500, 500, 500, 500], f"expected app-level 500s before breach, got {statuses}")
        self.assertEqual(statuses[5], 429, f"expected 429 on 6th call, got {statuses}")

    def test_detect_business_limited(self):
        with patch("chaos_tester.modules.business_identifier.BusinessIdentifier") as mock_identifier:
            mock_identifier.return_value.identify.return_value = {
                "business_name": "Example Inc.",
                "location": "Example City, US",
                "sector": "software",
                "lookup_source": "mock",
                "candidates": [],
            }
            statuses = [self._post("/api/detect-business", {"url": "https://example.com"}).status_code for _ in range(11)]
        self.assertEqual(statuses[:10], [200] * 10, f"expected first 10 calls accepted, got {statuses}")
        self.assertEqual(statuses[10], 429, f"expected 429 on 11th call, got {statuses}")


if __name__ == "__main__":
    unittest.main()
