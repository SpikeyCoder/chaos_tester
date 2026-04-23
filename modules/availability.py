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
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from typing import List, Set

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from .base import BaseModule
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger("chaos_tester")


class AvailabilityScanner(BaseModule):

    MODULE_NAME = "availability"

    SLOW_THRESHOLD_MS = 3000
    VERY_SLOW_THRESHOLD_MS = 8000

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        """Crawl and test every discovered page concurrently."""
        # Mount a connection pool adapter for efficient crawling and page testing
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.page_cache: dict = {}
        pages = discovered_pages or self._crawl()
        logger.info(f"[availability] Testing {len(pages)} pages concurrently")

        workers = min(self.config.concurrency, len(pages)) if pages else 1
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._test_page, url): url for url in pages}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.warning("Availability test failed for %s: %s", futures[future], exc)

        return self.results

    # -- Crawler -------------------------------------------------------

    def _crawl(self) -> List[str]:
        """BFS crawl from base_url in parallel using 20 workers (continuous, no batch-wait)."""
        import threading
        visited: Set[str] = set()
        visited_lock = threading.Lock()
        _cache_lock = threading.Lock()

        seeds = [self.config.base_url] + list(self.config.seed_urls)
        for s in seeds:
            s = urldefrag(s)[0]
            if self._is_same_domain(s) and not any(ex in s for ex in self.config.excluded_paths):
                visited.add(s)

        def _fetch_links(url: str, depth: int):
            """Fetch a page and return newly discovered links."""
            new_links = []
            try:
                resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
                with _cache_lock:
                    self.page_cache[url] = (resp, err, dt)
                if err or not resp:
                    return new_links
                if "text/html" not in resp.headers.get("content-type", ""):
                    return new_links
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = urljoin(url, a["href"])
                    href = urldefrag(href)[0]
                    if self._is_same_domain(href) and not any(ex in href for ex in self.config.excluded_paths):
                        new_links.append((href, depth + 1))
            except Exception as e:
                logger.debug(f"[crawl] Error fetching {url}: {e}")
            return new_links

        with ThreadPoolExecutor(max_workers=20) as executor:
            # Submit all seeds immediately
            pending = {}
            for s in visited:
                if len(visited) < self.config.max_pages:
                    pending[executor.submit(_fetch_links, s, 0)] = (s, 0)

            # Continuously process completed futures and submit new work without waiting
            # for the whole batch — eliminates the slowest-URL-blocks-next-batch problem.
            while pending:
                done, _ = wait(list(pending.keys()), return_when=FIRST_COMPLETED)
                for future in done:
                    pending.pop(future)
                    try:
                        new_links = future.result()
                        with visited_lock:
                            for href, new_depth in new_links:
                                if (href not in visited
                                        and len(visited) < self.config.max_pages
                                        and new_depth < self.config.crawl_depth):
                                    visited.add(href)
                                    pending[executor.submit(_fetch_links, href, new_depth)] = (href, new_depth)
                    except Exception as e:
                        logger.debug(f"[crawl] Fetch error: {e}")

        logger.info(f"[availability] Discovered {len(visited)} pages")
        return sorted(visited)

    # -- Individual page test ------------------------------------------

    def _test_page(self, url: str):
        cached = self.page_cache.get(url)
        if cached is not None:
            resp, err, dt = cached
        else:
            resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)

        if err:
            self.add_result(
                name=f"Page load: {self._short(url)}",
                description=f"GET {url}",
                status=TestStatus.FAILED,
                severity=Severity.HIGH,
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
            sev = Severity.CRITICAL
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
                ("internal server error", Severity.CRITICAL),
                ("traceback (most recent call last)", Severity.CRITICAL),
                ("exception in", Severity.MEDIUM),
                ("fatal error", Severity.CRITICAL),
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
