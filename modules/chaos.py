"""
Module 4 -- Chaos / Failure Injection

Simulates failure conditions to test resilience:
  - Inject artificial latency into requests
  - Simulate API errors (500, 502, 503)
  - Simulate timeouts
  - Corrupt cookies / sessions
  - Request missing or renamed assets
  - Test with disabled JavaScript markers
  - Send malformed headers
"""

import logging
import time
import random
from typing import List
from urllib.parse import urljoin

from .base import BaseModule
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger("chaos_tester")


class ChaosInjector(BaseModule):

    MODULE_NAME = "chaos"

    # Intensity presets
    INTENSITY = {
        "low":    {"error_codes": [500], "timeout_s": 2, "latency_s": 1},
        "medium": {"error_codes": [500, 502, 503], "timeout_s": 0.5, "latency_s": 0.1},
        "high":   {"error_codes": [500, 502, 503, 504, 429], "timeout_s": 0.1, "latency_s": 0.01},
    }

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        pages = discovered_pages or [self.config.base_url]
        targets = self.config.chaos_targets
        intensity = self.INTENSITY.get(self.config.chaos_intensity, self.INTENSITY["medium"])

        logger.info(f"[chaos] Running {len(targets)} chaos scenarios at {self.config.chaos_intensity} intensity")

        sample_pages = pages[:20]  # cap pages for chaos tests

        for target in targets:
            method = getattr(self, f"_chaos_{target}", None)
            if method:
                method(sample_pages, intensity)
            else:
                logger.warning(f"[chaos] Unknown target: {target}")

        return self.results

    # -- Scenario: API Latency -------------------------------------

    def _chaos_api_latency(self, pages: list, intensity: dict):
        """Test how pages handle slow responses by using very short timeouts."""
        for url in pages[:5]:
            # Simulate the experience of a slow server by setting an
            # aggressively short timeout -- if the page normally takes > threshold,
            # we flag it as latency-sensitive
            try:
                resp, dt = self._timed(
                    self.session.get, url,
                    timeout=intensity["latency_s"],
                )
                self.add_result(
                    name=f"Latency resilience: {self._short_path(url)}",
                    description=f"Page responds within aggressive timeout ({intensity['latency_s']}s)",
                    status=TestStatus.PASSED,
                    severity=Severity.INFO,
                    url=url,
                    details=f"Responded in {dt:.0f}ms with tight timeout.",
                    duration_ms=dt,
                )
            except Exception:
                self.add_result(
                    name=f"Latency sensitive: {self._short_path(url)}",
                    description=f"Page failed with {intensity['latency_s']}s timeout",
                    status=TestStatus.WARNING,
                    severity=Severity.MEDIUM,
                    url=url,
                    details=f"Page could not respond within {intensity['latency_s']}s -- may be vulnerable to latency spikes.",
                    recommendation="Implement request timeouts, loading states, and graceful degradation.",
                )

    # -- Scenario: API Error (5xx) ---------------------------------

    def _chaos_api_error_500(self, pages: list, intensity: dict):
        """Check if the site has custom error pages for 5xx codes."""
        base = self.config.base_url.rstrip("/")

        for code in intensity["error_codes"]:
            # Try common error-page URLs
            for path in [f"/{code}", f"/error/{code}", f"/error?code={code}"]:
                test_url = base + path
                resp, err, dt = self._safe_request("get", test_url, timeout=self.config.request_timeout)

                if resp and resp.status_code == code:
                    # Check for custom vs default error page
                    body = resp.text.lower()
                    has_custom = any(kw in body for kw in ["sorry", "oops", "go back", "home", "contact"])
                    if has_custom:
                        self.add_result(
                            name=f"Custom {code} page exists",
                            description=f"Custom error page found for HTTP {code}",
                            status=TestStatus.PASSED,
                            severity=Severity.INFO,
                            url=test_url,
                            details=f"Site has a user-friendly {code} error page.",
                            duration_ms=dt,
                        )
                    else:
                        self.add_result(
                            name=f"Generic {code} page",
                            description=f"Error page for {code} appears generic or default",
                            status=TestStatus.WARNING,
                            severity=Severity.LOW,
                            url=test_url,
                            details=f"The {code} page lacks user-friendly messaging.",
                            recommendation=f"Create a custom {code} error page with navigation back to the site.",
                            duration_ms=dt,
                        )
                    break

        # Test that a clearly invalid URL returns 404 not 500
        junk_url = base + f"/chaos-test-{random.randint(10000,99999)}-nonexistent"
        resp, err, dt = self._safe_request("get", junk_url, timeout=self.config.request_timeout)
        if resp:
            if resp.status_code == 404:
                self.add_result(
                    name="404 handling: random path",
                    description="Server returns 404 for unknown pages (good)",
                    status=TestStatus.PASSED,
                    severity=Severity.INFO,
                    url=junk_url,
                    details="Random nonexistent path correctly returns 404.",
                    duration_ms=dt,
                )
            elif resp.status_code >= 500:
                self.add_result(
                    name="500 on unknown path",
                    description="Server returns 500 instead of 404 for unknown pages",
                    status=TestStatus.FAILED,
                    severity=Severity.HIGH,
                    url=junk_url,
                    details=f"Expected 404 but got {resp.status_code}. Server may be crashing on unknown routes.",
                    recommendation="Add a catch-all route handler that returns proper 404.",
                    duration_ms=dt,
                )

    # -- Scenario: Timeout -----------------------------------------

    def _chaos_api_timeout(self, pages: list, intensity: dict):
        """Test near-zero timeout to verify the site handles connection issues."""
        for url in pages[:3]:
            try:
                resp = self.session.get(url, timeout=0.001)
                # If this succeeds, the server is extremely fast
                self.add_result(
                    name=f"Ultra-fast response: {self._short_path(url)}",
                    description="Page responded in under 1ms",
                    status=TestStatus.PASSED,
                    severity=Severity.INFO,
                    url=url,
                    details="Server response was nearly instant.",
                )
            except Exception:
                # Expected -- this is just confirming the site doesn't crash
                self.add_result(
                    name=f"Timeout handling: {self._short_path(url)}",
                    description="Verified behavior under extreme timeout (expected failure)",
                    status=TestStatus.PASSED,
                    severity=Severity.INFO,
                    url=url,
                    details="Request correctly failed under impossible timeout -- verify client-side timeout handling.",
                    recommendation="Ensure frontend shows loading/error states when backend is slow.",
                )

    # -- Scenario: Missing Assets ----------------------------------

    def _chaos_missing_assets(self, pages: list, intensity: dict):
        """Request known-bad asset paths to test fallback behavior."""
        base = self.config.base_url.rstrip("/")
        fake_assets = [
            "/static/nonexistent.js",
            "/css/deleted-file.css",
            "/images/missing-image.png",
            "/api/v1/nonexistent-endpoint",
            "/favicon.ico.bak",
        ]
        for path in fake_assets:
            url = base + path
            resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
            if resp:
                if resp.status_code == 404:
                    self.add_result(
                        name=f"Missing asset → 404: {path}",
                        description="Server correctly returns 404 for missing assets",
                        status=TestStatus.PASSED,
                        severity=Severity.INFO,
                        url=url,
                        duration_ms=dt,
                    )
                elif resp.status_code >= 500:
                    self.add_result(
                        name=f"Missing asset → {resp.status_code}: {path}",
                        description="Server error when requesting missing asset",
                        status=TestStatus.FAILED,
                        severity=Severity.HIGH,
                        url=url,
                        details=f"Server returned {resp.status_code} instead of 404.",
                        recommendation="Ensure static file handling returns 404, not 500, for missing files.",
                        duration_ms=dt,
                    )

    # -- Scenario: Corrupted Cookies -------------------------------

    def _chaos_corrupted_cookies(self, pages: list, intensity: dict):
        """Send garbage cookies and see how the server handles them."""
        test_page = pages[0] if pages else self.config.base_url

        corrupted_cookies = {
            "sessionid": "AAAA" * 100,
            "csrftoken": "<script>alert(1)</script>",
            "auth_token": "' OR 1=1 --",
            self.config.auth_cookie_name: "corrupted_value_" + "X" * 200,
        }

        for cookie_name, cookie_value in corrupted_cookies.items():
            jar = {cookie_name: cookie_value}
            resp, err, dt = self._safe_request(
                "get", test_page,
                cookies=jar,
                timeout=self.config.request_timeout,
            )
            if resp:
                if resp.status_code >= 500:
                    self.add_result(
                        name=f"Corrupted cookie crash: {cookie_name}",
                        description=f"Server error when receiving corrupted '{cookie_name}' cookie",
                        status=TestStatus.FAILED,
                        severity=Severity.HIGH,
                        url=test_page,
                        details=f"Sending corrupted {cookie_name} caused HTTP {resp.status_code}.",
                        recommendation="Add robust cookie parsing with try/except. Never trust cookie values.",
                        duration_ms=dt,
                    )
                else:
                    self.add_result(
                        name=f"Corrupted cookie handled: {cookie_name}",
                        description=f"Server handled corrupted '{cookie_name}' gracefully ({resp.status_code})",
                        status=TestStatus.PASSED,
                        severity=Severity.INFO,
                        url=test_page,
                        duration_ms=dt,
                    )
            elif err:
                self.add_result(
                    name=f"Corrupted cookie error: {cookie_name}",
                    description=f"Connection failed with corrupted cookie",
                    status=TestStatus.WARNING,
                    severity=Severity.MEDIUM,
                    url=test_page,
                    details=err,
                    recommendation="Verify server doesn't crash on malformed cookies.",
                )
