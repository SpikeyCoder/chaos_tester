"""
Module 1 -- Page Availability Scanner

Crawls from the base URL, discovers pages, and checks:
  - HTTP status codes (200, 3xx, 4xx, 5xx)
  - Response time thresholds
  - Expected content presence
  - Redirect chains
"""

import logging
import re
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
from typing import List, Set

from bs4 import BeautifulSoup

from .base import BaseModule
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger("chaos_tester")


class AvailabilityScanner(BaseModule):

    MODULE_NAME = "availability"

    SLOW_THRESHOLD_MS = 3000
    VERY_SLOW_THRESHOLD_MS = 8000

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        """Crawl and test every discovered page."""
        pages = discovered_pages or self._crawl()
        logger.info(f"[availability] Testing {len(pages)} pages")

        for url in pages:
            self._test_page(url)

        return self.results

    # -- Crawler -------------------------------------------------------

    def _crawl(self) -> List[str]:
        """BFS crawl from base_url, returning a list of internal URLs."""
        visited: Set[str] = set()
        queue = deque()

        seeds = [self.config.base_url] + list(self.config.seed_urls)
        for s in seeds:
            queue.append((s, 0))

        while queue and len(visited) < self.config.max_pages:
            url, depth = queue.popleft()
            url = urldefrag(url)[0]

            if url in visited:
                continue
            if not self._is_same_domain(url):
                continue
            if any(ex in url for ex in self.config.excluded_paths):
                continue

            visited.add(url)

            if depth >= self.config.crawl_depth:
                continue

            # Fetch and extract links
            try:
                resp = self._get(url)
                if "text/html" not in resp.headers.get("content-type", ""):
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = urljoin(url, a["href"])
                    href = urldefrag(href)[0]
                    if self._is_same_domain(href) and href not in visited:
                        queue.append((href, depth + 1))
            except Exception as e:
                logger.debug(f"[crawl] Error fetching {url}: {e}")

        logger.info(f"[availability] Discovered {len(visited)} pages")
        return sorted(visited)

    # -- Individual page test ------------------------------------------

    def _test_page(self, url: str):
        resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)

        if err:
            # Only critical if this is the site root (home page completely down)
            is_root = urlparse(url).path in ("", "/")
            self.add_result(
                name=f"Page load: {self._short(url)}",
                description=f"GET {url}",
                status=TestStatus.FAILED,
                severity=Severity.CRITICAL if is_root else Severity.HIGH,
                url=url,
                details=err,
                recommendation="Investigate server connectivity or DNS resolution.",
                duration_ms=dt,
            )
            return

        status = resp.status_code

        # -- Status code check -------------------------------------
        if 200 <= status < 300:
            test_status = TestStatus.PASSED
            sev = Severity.INFO
            detail = f"HTTP {status} OK"
            rec = ""
        elif 300 <= status < 400:
            test_status = TestStatus.WARNING
            sev = Severity.LOW
            loc = resp.headers.get("Location", "unknown")
            detail = f"Redirect {status} → {loc}"
            rec = "Verify redirect target is intentional."
        elif status == 403:
            test_status = TestStatus.WARNING
            sev = Severity.MEDIUM
            detail = f"HTTP 403 Forbidden"
            rec = "Check access control -- page may be intentionally restricted."
        elif status == 404:
            test_status = TestStatus.FAILED
            sev = Severity.HIGH
            detail = f"HTTP 404 Not Found"
            rec = "Remove or fix dead link; add a custom 404 page."
        elif 500 <= status < 600:
            test_status = TestStatus.FAILED
            sev = Severity.HIGH
            detail = f"HTTP {status} Server Error"
            rec = "Investigate server logs immediately."
        else:
            test_status = TestStatus.WARNING
            sev = Severity.MEDIUM
            detail = f"Unexpected HTTP {status}"
            rec = "Review whether this status code is intentional."

        self.add_result(
            name=f"Page load: {self._short(url)}",
            description=f"GET {url}",
            status=test_status,
            severity=sev,
            url=url,
            details=detail,
            recommendation=rec,
            duration_ms=dt,
        )

        # -- Response time check -----------------------------------
        if dt > self.VERY_SLOW_THRESHOLD_MS:
            self.add_result(
                name=f"Slow response: {self._short(url)}",
                description=f"Response took {dt:.0f}ms",
                status=TestStatus.WARNING,
                severity=Severity.MEDIUM,
                url=url,
                details=f"Response time {dt:.0f}ms exceeds {self.VERY_SLOW_THRESHOLD_MS}ms threshold.",
                recommendation="Profile server performance; check DB queries and asset loading.",
                duration_ms=dt,
            )
        elif dt > self.SLOW_THRESHOLD_MS:
            self.add_result(
                name=f"Slow response: {self._short(url)}",
                description=f"Response took {dt:.0f}ms",
                status=TestStatus.WARNING,
                severity=Severity.MEDIUM,
                url=url,
                details=f"Response time {dt:.0f}ms exceeds {self.SLOW_THRESHOLD_MS}ms threshold.",
                recommendation="Consider caching, CDN, or query optimization.",
                duration_ms=dt,
            )

        # -- Check for error text in HTML --------------------------
        if 200 <= status < 300 and "text/html" in resp.headers.get("content-type", ""):
            body_lower = resp.text[:5000].lower()
            error_patterns = [
                ("internal server error", Severity.HIGH),
                ("traceback (most recent call last)", Severity.HIGH),
                ("exception in", Severity.MEDIUM),
                ("fatal error", Severity.HIGH),
                ("syntax error", Severity.MEDIUM),
                ("undefined variable", Severity.LOW),
            ]
            for pattern, sev in error_patterns:
                if pattern in body_lower:
                    self.add_result(
                        name=f"Error text in page: {self._short(url)}",
                        description=f"Found '{pattern}' in HTML body",
                        status=TestStatus.FAILED,
                        severity=sev,
                        url=url,
                        details=f"Page returned 200 but contains error text: '{pattern}'",
                        recommendation="Fix the error or ensure debug output is disabled in staging/production.",
                        duration_ms=dt,
                    )
                    break  # one error per page is enough

    def _short(self, url: str) -> str:
        path = urlparse(url).path or "/"
        return path[:60]
