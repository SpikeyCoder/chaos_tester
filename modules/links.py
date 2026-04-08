"""
Module 2 -- Broken Link Scanner

Finds all internal and external links, images, scripts, and stylesheets
across discovered pages and verifies they resolve.
"""

import logging
from urllib.parse import urljoin, urlparse, urldefrag
from typing import List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from .base import BaseModule
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger("chaos_tester")


class BrokenLinkScanner(BaseModule):

    MODULE_NAME = "links"

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        pages = discovered_pages or [self.config.base_url]
        logger.info(f"[links] Scanning links on {len(pages)} pages")

        # Collect all unique resources across pages in parallel
        import threading
        resource_map: dict = {}  # url -> set of source pages
        resource_map_lock = threading.Lock()

        def _collect(page_url: str):
            resources = self._extract_resources(page_url)
            with resource_map_lock:
                for res_url, res_type in resources:
                    resource_map.setdefault(res_url, {"type": res_type, "sources": set()})
                    resource_map[res_url]["sources"].add(page_url)

        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            list(executor.map(_collect, pages))

        logger.info(f"[links] Found {len(resource_map)} unique resources to verify")

        # Check each resource (with concurrency)
        checked: Set[str] = set()
        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            futures = {}
            for url, info in resource_map.items():
                if url in checked:
                    continue
                checked.add(url)
                futures[executor.submit(self._check_resource, url, info["type"])] = (url, info)

            for future in as_completed(futures):
                url, info = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.debug(f"[links] Error checking {url}: {e}")

        return self.results

    def _extract_resources(self, page_url: str) -> List[Tuple[str, str]]:
        """Extract all linkable resources from a page."""
        resources = []
        try:
            resp = self._get(page_url)
            if "text/html" not in resp.headers.get("content-type", ""):
                return resources
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception:
            return resources

        # <a href>
        for a in soup.find_all("a", href=True):
            href = urldefrag(urljoin(page_url, a["href"]))[0]
            if href.startswith(("http://", "https://")):
                resources.append((href, "link"))

        # <img src> — skip data: URIs (inline SVG/base64 images are not broken)
        for img in soup.find_all("img", src=True):
            raw_src = img["src"].strip()
            if raw_src.startswith("data:"):
                continue  # F-06: data URIs are valid inline images, not broken
            src = urljoin(page_url, raw_src)
            resources.append((src, "image"))

        # <script src>
        for s in soup.find_all("script", src=True):
            src = urljoin(page_url, s["src"])
            resources.append((src, "script"))

        # <link rel="stylesheet" href> (skip preconnect, dns-prefetch, preload, etc.)
        for link in soup.find_all("link", href=True):
            rel = " ".join(link.get("rel", []))
            if rel != "stylesheet":
                continue
            href = urljoin(page_url, link["href"])
            resources.append((href, "stylesheet"))

        return resources

    def _check_resource(self, url: str, res_type: str):
        """HEAD-check a resource URL."""
        try:
            resp, dt = self._timed(
                self.session.head, url,
                timeout=self.config.request_timeout,
                allow_redirects=True,
            )
            status = resp.status_code
        except Exception as e:
            # mailto: and tel: links are not broken -- they're non-HTTP protocols
            parsed = urlparse(url)
            if parsed.scheme in ("mailto", "tel", "javascript"):
                self.add_result(
                    name=f"Non-HTTP {res_type}: {self._short_url(url)}",
                    description=f"Non-HTTP link ({parsed.scheme}:) -- not a broken link",
                    status=TestStatus.PASSED,
                    severity=Severity.INFO,
                    url=url,
                    details=f"Protocol {parsed.scheme}: is not checked for reachability.",
                    duration_ms=0,
                )
                return
            self.add_result(
                name=f"Broken {res_type}: {self._short_url(url)}",
                description=f"Could not reach {res_type}: {url}",
                status=TestStatus.WARNING,
                severity=Severity.MEDIUM if res_type == "link" else Severity.LOW,
                url=url,
                details=f"Connection failed: {e}",
                recommendation=f"Fix or remove the broken {res_type} reference.",
                duration_ms=0,
            )
            return

        if status == 405:
            # HEAD not allowed -- try GET
            try:
                resp, dt = self._timed(
                    self.session.get, url,
                    timeout=self.config.request_timeout,
                    allow_redirects=True,
                    stream=True,
                )
                status = resp.status_code
                resp.close()
            except Exception:
                pass

        if status >= 400:
            sev = Severity.MEDIUM if status >= 500 else Severity.LOW
            self.add_result(
                name=f"Broken {res_type} ({status}): {self._short_url(url)}",
                description=f"{res_type.capitalize()} returned HTTP {status}",
                status=TestStatus.WARNING,
                severity=sev,
                url=url,
                details=f"HTTP {status} for {res_type}: {url}",
                recommendation=f"Fix or remove the broken {res_type}. Status {status}.",
                duration_ms=dt,
            )
        else:
            self.add_result(
                name=f"{res_type.capitalize()} OK: {self._short_url(url)}",
                description=f"{res_type.capitalize()} resolved successfully",
                status=TestStatus.PASSED,
                severity=Severity.INFO,
                url=url,
                details=f"HTTP {status}",
                duration_ms=dt,
            )

    def _short_url(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path or "/"
        if len(path) > 50:
            path = path[:47] + "..."
        return f"{parsed.netloc}{path}"
