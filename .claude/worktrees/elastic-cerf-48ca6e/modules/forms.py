"""
Module 3 -- Form & Button Interaction Tester

Discovers forms and interactive elements across pages and tests:
  - Form submission with empty fields (validation check)
  - Form submission with invalid data (XSS-like, SQL-like)
  - Button clickability and action endpoints
  - CSRF token presence
  - Required field enforcement
"""

import logging
import re
from urllib.parse import urljoin
from typing import List

from bs4 import BeautifulSoup

from .base import BaseModule
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger("chaos_tester")


class FormInteractionTester(BaseModule):

    MODULE_NAME = "forms"

    # Payloads for testing input handling (non-destructive)
    FUZZ_PAYLOADS = {
        "empty": "",
        "xss_basic": "<script>alert(1)</script>",
        "sql_basic": "' OR '1'='1",
        "long_string": "A" * 5000,
        "special_chars": "!@#$%^&*(){}|:<>?`~",
        "null_byte": "test\x00value",
        "unicode": "テスト",
    }

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        pages = discovered_pages or [self.config.base_url]
        logger.info(f"[forms] Scanning forms on {len(pages)} pages concurrently")

        workers = min(self.config.concurrency, len(pages), 8)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._scan_page, url): url for url in pages}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.warning("Forms scan failed for %s: %s", futures[future], exc)

        return self.results

    def _scan_page(self, page_url: str):
        resp, err, dt = self._safe_request("get", page_url, timeout=self.config.request_timeout)
        if err or not resp:
            return
        if "text/html" not in resp.headers.get("content-type", ""):
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        forms = soup.find_all("form")

        for idx, form in enumerate(forms):
            self._test_form(page_url, form, idx)

        # Check for buttons outside forms that default to type="submit"
        # Buttons with explicit type="button" are intentionally JS-driven and
        # don't need a form wrapper, so we exclude them from this check.
        buttons = soup.find_all("button")
        buttons += soup.find_all("input", {"type": "submit"})
        buttons += soup.find_all("a", {"role": "button"})
        standalone_buttons = [
            b for b in buttons
            if not b.find_parent("form")
            and b.get("type", "").lower() != "button"
        ]

        if standalone_buttons:
            self.add_result(
                name=f"Standalone buttons: {self._short_path(page_url)}",
                description=f"Found {len(standalone_buttons)} button(s) outside <form> tags without type=\"button\"",
                status=TestStatus.WARNING,
                severity=Severity.LOW,
                url=page_url,
                details=f"Buttons: {[self._button_label(b) for b in standalone_buttons[:5]]}",
                recommendation="Add type=\"button\" to JS-driven buttons, or wrap submit buttons in a <form>.",
            )

    def _test_form(self, page_url: str, form, idx: int):
        action = form.get("action", "")
        method = form.get("method", "get").lower()
        form_url = urljoin(page_url, action) if action else page_url
        form_id = form.get("id", form.get("name", f"form_{idx}"))

        inputs = form.find_all(["input", "textarea", "select"])
        input_names = []
        required_fields = []
        has_csrf = False

        for inp in inputs:
            name = inp.get("name", "")
            if not name:
                continue
            input_names.append(name)

            if inp.has_attr("required") or inp.get("aria-required") == "true":
                required_fields.append(name)

            if name.lower() in ("csrf", "csrfmiddlewaretoken", "_token", "csrf_token", "authenticity_token"):
                has_csrf = True
            if inp.get("type", "").lower() == "hidden" and "csrf" in name.lower():
                has_csrf = True

        # -- CSRF check --------------------------------------------
        if method == "post" and not has_csrf:
            self.add_result(
                name=f"Missing CSRF token: {form_id}",
                description=f"POST form on {self._short_path(page_url)} lacks CSRF protection",
                status=TestStatus.FAILED,
                severity=Severity.HIGH,
                url=page_url,
                details=f"Form '{form_id}' (action={action}) uses POST but has no CSRF token field.",
                recommendation="Add CSRF token to all POST forms to prevent cross-site request forgery.",
            )

        # -- Empty submission test ---------------------------------
        if method == "post" and input_names:
            empty_data = {name: "" for name in input_names}
            resp, err, dt = self._safe_request(
                "post", form_url, data=empty_data,
                timeout=self.config.request_timeout,
            )
            if resp:
                if resp.status_code == 500:
                    self.add_result(
                        name=f"Empty submit crashes: {form_id}",
                        description=f"Submitting empty data caused HTTP 500",
                        status=TestStatus.FAILED,
                        severity=Severity.HIGH,
                        url=form_url,
                        details=f"POST {form_url} with empty fields returned 500.",
                        recommendation="Add server-side validation; never trust client-side validation alone.",
                        duration_ms=dt,
                    )
                elif resp.status_code < 400:
                    self.add_result(
                        name=f"Empty submit accepted: {form_id}",
                        description=f"Form accepted empty data without error",
                        status=TestStatus.WARNING,
                        severity=Severity.MEDIUM,
                        url=form_url,
                        details=f"POST {form_url} with empty fields returned {resp.status_code}.",
                        recommendation="Ensure required field validation is enforced server-side.",
                        duration_ms=dt,
                    )
                else:
                    self.add_result(
                        name=f"Empty submit rejected: {form_id}",
                        description=f"Server correctly rejected empty data ({resp.status_code})",
                        status=TestStatus.PASSED,
                        severity=Severity.INFO,
                        url=form_url,
                        details=f"Good: empty form submission was rejected.",
                        duration_ms=dt,
                    )

        # -- XSS / injection payload test --------------------------
        if method == "post" and input_names:
            xss_data = {name: self.FUZZ_PAYLOADS["xss_basic"] for name in input_names}
            resp, err, dt = self._safe_request(
                "post", form_url, data=xss_data,
                timeout=self.config.request_timeout,
            )
            if resp and self.FUZZ_PAYLOADS["xss_basic"] in resp.text:
                self.add_result(
                    name=f"Reflected XSS risk: {form_id}",
                    description=f"XSS payload reflected in response body",
                    status=TestStatus.FAILED,
                    severity=Severity.CRITICAL,
                    url=form_url,
                    details="Script tag was echoed back unescaped in the server response.",
                    recommendation="Sanitize and escape all user input. Use Content-Security-Policy headers.",
                    duration_ms=dt,
                )

        # -- Required fields check ---------------------------------
        if required_fields:
            self.add_result(
                name=f"Required fields: {form_id}",
                description=f"Form declares {len(required_fields)} required field(s)",
                status=TestStatus.PASSED,
                severity=Severity.INFO,
                url=page_url,
                details=f"Required: {required_fields[:10]}",
            )
        elif input_names:
            self.add_result(
                name=f"No required fields: {form_id}",
                description=f"Form has {len(input_names)} inputs but none marked required",
                status=TestStatus.WARNING,
                severity=Severity.LOW,
                url=page_url,
                details="No 'required' attributes found on form inputs.",
                recommendation="Consider marking essential fields as required for better validation.",
            )

    def _button_label(self, btn) -> str:
        text = btn.get_text(strip=True)[:30]
        return text or btn.get("value", btn.get("aria-label", "unlabeled"))
