"""
Regression tests for the user-provided business name override.

Bug: the dashboard lets the user correct a mis-detected business name
(hidden ``business_name`` form field), but /run never copied that field
into ChaosConfig, and the AI Visibility scanner re-ran server-side
detection — so the audit executed with the wrong business name.

Asserts that:
  - /run copies ``business_name`` from the request payload into ChaosConfig
    (and tolerates non-string JSON values instead of raising a 500)
  - AIVisibilityScanner._extract_business_info prefers the user-provided
    name over the server-side detected one
  - when the corrected name differs from the detected one, the sector is
    re-derived from the corrected name (queries are built from sector +
    location, so a sector keyed to the wrong name would still target the
    wrong business) and name-keyed location lookups are redone
  - detection still wins when the user provided nothing
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_PARENT = Path(__file__).resolve().parents[2]
if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))

os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")
os.environ.setdefault("CHAOS_TESTER_SECRET_KEY", "test-key-32-bytes-test-key-32-bytes")

from chaos_tester.config import ChaosConfig
from chaos_tester.modules.ai_visibility import AIVisibilityScanner

DETECTED = {
    "business_name": "Find Grants for Nonprofits",
    "location": "Seattle, WA",
    "sector": "nonprofit services",
    "lookup_source": "structured_data",
    "candidates": [],
}


def _make_scanner(detected=None, **config_overrides) -> AIVisibilityScanner:
    config = ChaosConfig(base_url="https://fundermatch.org", **config_overrides)
    scanner = AIVisibilityScanner(config, session=MagicMock())
    scanner._identifier = MagicMock()
    scanner._identifier.identify.return_value = dict(detected or DETECTED)
    scanner._identifier.detect_sector.return_value = "holding company services"
    scanner._identifier.lookup_headquarters.return_value = ("Tacoma, WA", "irs_eo")
    return scanner


class UserBusinessNameWinsInScanner(unittest.TestCase):
    def test_user_provided_name_overrides_detected(self):
        scanner = _make_scanner(business_name="Armstrong HoldCo LLC")
        info = scanner._extract_business_info("https://fundermatch.org")
        self.assertEqual(info["business_name"], "Armstrong HoldCo LLC")
        self.assertEqual(scanner.business_name, "Armstrong HoldCo LLC")

    def test_detected_name_used_when_no_override(self):
        scanner = _make_scanner()
        info = scanner._extract_business_info("https://fundermatch.org")
        self.assertEqual(info["business_name"], "Find Grants for Nonprofits")
        scanner._identifier.detect_sector.assert_not_called()

    def test_whitespace_only_override_falls_back_to_detected(self):
        scanner = _make_scanner(business_name="   ")
        info = scanner._extract_business_info("https://fundermatch.org")
        self.assertEqual(info["business_name"], "Find Grants for Nonprofits")

    def test_user_name_wins_even_when_identifier_fails(self):
        scanner = _make_scanner(business_name="Armstrong HoldCo LLC")
        scanner._identifier.identify.side_effect = RuntimeError("boom")
        info = scanner._extract_business_info("https://fundermatch.org")
        self.assertEqual(info["business_name"], "Armstrong HoldCo LLC")


class SectorAndLocationRederivedForCorrectedName(unittest.TestCase):
    """Queries are generated from sector + location, both derived from the
    detected name — so correcting only the name would still score against the
    wrong business's sector/city."""

    def test_sector_rederived_from_corrected_name(self):
        scanner = _make_scanner(business_name="Armstrong HoldCo LLC")
        info = scanner._extract_business_info("https://fundermatch.org", "<html>page</html>")
        scanner._identifier.detect_sector.assert_called_once_with(
            "Armstrong HoldCo LLC", "<html>page</html>"
        )
        self.assertEqual(info["sector"], "holding company services")

    def test_sector_kept_when_override_matches_detected_name(self):
        scanner = _make_scanner(business_name="  find grants for NONPROFITS ")
        info = scanner._extract_business_info("https://fundermatch.org")
        scanner._identifier.detect_sector.assert_not_called()
        self.assertEqual(info["sector"], "nonprofit services")

    def test_name_keyed_location_redone_for_corrected_name(self):
        detected = dict(DETECTED, lookup_source="google_places")
        scanner = _make_scanner(detected=detected, business_name="Armstrong HoldCo LLC")
        info = scanner._extract_business_info("https://fundermatch.org", "<html/>")
        scanner._identifier.lookup_headquarters.assert_called_once_with(
            "Armstrong HoldCo LLC", "https://fundermatch.org", "<html/>"
        )
        self.assertEqual(info["location"], "Tacoma, WA")

    def test_page_based_location_kept_for_corrected_name(self):
        # structured_data comes from the page, not the (wrong) name — keep it
        scanner = _make_scanner(business_name="Armstrong HoldCo LLC")
        info = scanner._extract_business_info("https://fundermatch.org")
        scanner._identifier.lookup_headquarters.assert_not_called()
        self.assertEqual(info["location"], "Seattle, WA")

    def test_user_location_beats_relookup(self):
        detected = dict(DETECTED, lookup_source="irs_eo")
        scanner = _make_scanner(
            detected=detected,
            business_name="Armstrong HoldCo LLC",
            business_location="Bellingham, WA",
        )
        info = scanner._extract_business_info("https://fundermatch.org")
        scanner._identifier.lookup_headquarters.assert_not_called()
        self.assertEqual(info["location"], "Bellingham, WA")

    def test_rederivation_failure_keeps_detected_sector(self):
        scanner = _make_scanner(business_name="Armstrong HoldCo LLC")
        scanner._identifier.detect_sector.side_effect = RuntimeError("boom")
        info = scanner._extract_business_info("https://fundermatch.org")
        self.assertEqual(info["business_name"], "Armstrong HoldCo LLC")
        self.assertEqual(info["sector"], "nonprofit services")


class RunEndpointForwardsBusinessName(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import chaos_tester.app as app_module
        from chaos_tester.app import app, limiter

        app.config["TESTING"] = True
        limiter.reset()
        cls.app_module = app_module
        cls.app = app
        cls.client = app.test_client()
        cls.limiter = limiter

    def setUp(self):
        self.limiter.reset()
        self._reset_run_state()

    def tearDown(self):
        self._reset_run_state()

    def _reset_run_state(self):
        with self.app_module._lock:
            self.app_module._current_status = "idle"
            self.app_module._current_run = None
            self.app_module._progress.clear()
            self.app_module._highest_pct = 0

    def _post_run(self, payload):
        """POST /run with _run_tests stubbed; returns (response, config).

        /run hands the config to _run_tests on a worker thread. Capture it via
        side_effect + Event rather than polling mock.called (mock sets .called
        before .call_args, so a poll can win the race and read None) and rather
        than mocking threading.Thread (patching the shared threading module
        corrupts unrelated thread users, e.g. the limiter).
        """
        captured = []
        done = threading.Event()

        def _capture(config):
            captured.append(config)
            done.set()

        with patch("chaos_tester.app._run_tests", side_effect=_capture):
            response = self.client.post(
                "/run",
                data=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            if response.status_code == 202:
                self.assertTrue(done.wait(5), "worker thread never invoked _run_tests")

        return response, (captured[0] if captured else None)

    def test_run_copies_business_name_into_config(self):
        response, config = self._post_run({
            "base_url": "https://example.com",
            "business_name": "  Armstrong HoldCo LLC  ",
            "business_location": "Seattle, WA",
        })
        self.assertEqual(response.status_code, 202)
        self.assertEqual(config.business_name, "Armstrong HoldCo LLC")
        self.assertEqual(config.business_location, "Seattle, WA")

    def test_run_tolerates_non_string_business_name(self):
        # Crafted JSON (null/number) must not 500 the route
        response, config = self._post_run({
            "base_url": "https://example.com",
            "business_name": None,
            "business_location": 42,
        })
        self.assertEqual(response.status_code, 202)
        self.assertEqual(config.business_name, "")
        self.assertEqual(config.business_location, "42")


if __name__ == "__main__":
    unittest.main()
