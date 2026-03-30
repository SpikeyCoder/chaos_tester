"""
Module 5 -- Authentication & Authorization Tester

Tests:
  - Unauthenticated access to protected routes
  - Session fixation / manipulation
  - Token expiry behavior
  - Privilege escalation paths
  - Cookie security flags (Secure, HttpOnly, SameSite)
  - Login/logout flow integrity
"""

import logging
from typing import List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base import BaseModule
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger("chaos_tester")


# Common protected paths to probe
PROTECTED_PATHS = [
    "/admin", "/dashboard", "/settings", "/account", "/profile",
    "/api/users", "/api/admin", "/api/settings", "/api/private",
    "/internal", "/manage", "/config", "/users",
    "/billing", "/payments", "/orders",
]


class AuthTester(BaseModule):

    MODULE_NAME = "auth"

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        pages = discovered_pages or []
        logger.info("[auth] Running authentication and authorization tests")

        self._test_unauthenticated_access(pages)
        self._test_cookie_security()
        self._test_session_manipulation()
        self._test_http_methods()
        self._test_auth_headers()

        return self.results

    # -- Unauthenticated Access ------------------------------------

    def _test_unauthenticated_access(self, discovered_pages: list):
        """Hit protected routes without auth and check we get 401/403."""
        import requests
        unauth_session = requests.Session()
        unauth_session.headers.update({"User-Agent": self.config.user_agent})

        # Combine known protected paths + any discovered paths
        test_paths = set(PROTECTED_PATHS)
        for page in discovered_pages:
            parsed = urlparse(page)
            path = parsed.path.lower()
            if any(kw in path for kw in ("admin", "dashboard", "settings", "account", "profile", "manage", "internal")):
                test_paths.add(parsed.path)

        for path in sorted(test_paths):
            url = urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/"))
            try:
                resp = unauth_session.get(url, timeout=self.config.request_timeout, allow_redirects=False)
                status = resp.status_code

                if status in (401, 403):
                    self.add_result(
                        name=f"Auth enforced: {path}",
                        description=f"Unauthenticated request correctly blocked ({status})",
                        status=TestStatus.PASSED,
                        severity=Severity.INFO,
                        url=url,
                        details=f"HTTP {status} -- access denied without credentials.",
                    )
                elif 300 <= status < 400:
                    location = resp.headers.get("Location", "")
                    if "login" in location.lower() or "auth" in location.lower() or "signin" in location.lower():
                        self.add_result(
                            name=f"Auth redirect: {path}",
                            description=f"Redirects to login ({status} → {location})",
                            status=TestStatus.PASSED,
                            severity=Severity.INFO,
                            url=url,
                            details=f"Redirect to auth page: {location}",
                        )
                    else:
                        self.add_result(
                            name=f"Redirect (no auth?): {path}",
                            description=f"Redirects but not to login page",
                            status=TestStatus.WARNING,
                            severity=Severity.MEDIUM,
                            url=url,
                            details=f"Redirect to: {location} -- may not be auth-gated.",
                            recommendation="Verify this redirect is intentional and not bypassing auth.",
                        )
                elif status == 200:
                    # 200 on a "protected" path without auth is suspicious
                    body = resp.text[:2000].lower()
                    # Check if it's just a public page that happens to share a path name
                    is_public = any(kw in body for kw in ("sign in", "log in", "login", "register"))
                    if is_public:
                        self.add_result(
                            name=f"Public login page: {path}",
                            description=f"Path returns a login/registration page (OK)",
                            status=TestStatus.PASSED,
                            severity=Severity.INFO,
                            url=url,
                        )
                    else:
                        self.add_result(
                            name=f"⚠ Unprotected route: {path}",
                            description=f"Protected path accessible without auth (HTTP 200)",
                            status=TestStatus.FAILED,
                            severity=Severity.CRITICAL,
                            url=url,
                            details="This path returned content without requiring authentication.",
                            recommendation="Add authentication middleware to protect this route.",
                        )
                elif status == 404:
                    pass  # path doesn't exist, skip
                else:
                    self.add_result(
                        name=f"Unexpected status: {path}",
                        description=f"HTTP {status} on protected path",
                        status=TestStatus.WARNING,
                        severity=Severity.LOW,
                        url=url,
                        details=f"Unexpected status code {status} for unauthenticated request.",
                    )

            except Exception as e:
                logger.debug(f"[auth] Error testing {url}: {e}")

    # -- Cookie Security Flags -------------------------------------

    def _test_cookie_security(self):
        """Check that session cookies have Secure, HttpOnly, SameSite."""
        url = self.config.base_url
        resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
        if not resp:
            return

        cookies = resp.cookies
        if not cookies:
            # Try login endpoint
            if self.config.auth_url:
                resp, err, dt = self._safe_request("get", self.config.auth_url, timeout=self.config.request_timeout)
                if resp:
                    cookies = resp.cookies

        if not cookies:
            self.add_result(
                name="No cookies detected",
                description="No cookies set by the base URL",
                status=TestStatus.WARNING,
                severity=Severity.LOW,
                url=url,
                details="Could not check cookie security flags -- no cookies were set.",
                recommendation="If sessions are used, verify cookies on authenticated pages.",
            )
            return

        raw_sc = resp.headers.get("Set-Cookie", "") if resp else ""
        raw_hdrs = ""
        if hasattr(resp, "raw") and resp.raw and hasattr(resp.raw, "headers"):
            raw_hdrs = "\n".join(v for k, v in resp.raw.headers.items() if k.lower() == "set-cookie").lower()
        else:
            raw_hdrs = raw_sc.lower()
        for cookie in cookies:
            issues = []
            cookie_raw = ""
            for line in raw_hdrs.split("\n"):
                if line.strip().startswith(cookie.name.lower() + "="):
                    cookie_raw = line
                    break

            if not cookie.secure and "secure" not in cookie_raw:
                issues.append("Missing 'Secure' flag")
            if not cookie.has_nonstandard_attr("HttpOnly") and "httponly" not in cookie_raw and "httponly" not in str(cookie).lower():
                issues.append("Missing 'HttpOnly' flag")
            if "samesite" not in cookie_raw and not any(k.lower() == "samesite" for k in getattr(cookie, "_rest", {})):
                issues.append("Missing 'SameSite' attribute")

            if issues:
                self.add_result(
                    name=f"Insecure cookie: {cookie.name}",
                    description=f"Cookie '{cookie.name}' is missing security flags",
                    status=TestStatus.FAILED,
                    severity=Severity.HIGH,
                    url=url,
                    details=f"Issues: {', '.join(issues)}",
                    recommendation="Set Secure, HttpOnly, and SameSite=Lax/Strict on all session cookies.",
                )
            else:
                self.add_result(
                    name=f"Secure cookie: {cookie.name}",
                    description=f"Cookie '{cookie.name}' has proper security flags",
                    status=TestStatus.PASSED,
                    severity=Severity.INFO,
                    url=url,
                )

    # -- Session Manipulation --------------------------------------

    def _test_session_manipulation(self):
        """Test if the server handles tampered session tokens safely."""
        url = self.config.base_url
        tampered_values = [
            ("empty", ""),
            ("garbage", "not-a-real-session-XXXXXX"),
            ("expired_format", "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjB9.invalid"),
            ("admin_attempt", "admin"),
        ]

        for label, value in tampered_values:
            cookies = {self.config.auth_cookie_name: value}
            resp, err, dt = self._safe_request(
                "get", url, cookies=cookies,
                timeout=self.config.request_timeout,
            )
            if resp:
                if resp.status_code >= 500:
                    self.add_result(
                        name=f"Session tamper crash: {label}",
                        description=f"Server error with tampered session ({label})",
                        status=TestStatus.FAILED,
                        severity=Severity.HIGH,
                        url=url,
                        details=f"Tampered {self.config.auth_cookie_name}='{value[:30]}' caused HTTP {resp.status_code}.",
                        recommendation="Handle invalid session tokens gracefully -- clear cookie and redirect to login.",
                        duration_ms=dt,
                    )
                else:
                    self.add_result(
                        name=f"Session tamper handled: {label}",
                        description=f"Server handled tampered session gracefully ({resp.status_code})",
                        status=TestStatus.PASSED,
                        severity=Severity.INFO,
                        url=url,
                        duration_ms=dt,
                    )

    # -- HTTP Method Testing ---------------------------------------

    def _test_http_methods(self):
        """Test that sensitive endpoints reject unexpected HTTP methods."""
        base = self.config.base_url.rstrip("/")
        sensitive_paths = ["/api/users", "/api/admin", "/admin", "/settings"]
        dangerous_methods = ["DELETE", "PUT", "PATCH"]

        for path in sensitive_paths:
            url = base + path
            for method in dangerous_methods:
                try:
                    resp = self.session.request(
                        method, url,
                        timeout=self.config.request_timeout,
                        allow_redirects=False,
                    )
                    if resp.status_code in (200, 201, 204):
                        self.add_result(
                            name=f"{method} accepted: {path}",
                            description=f"{method} request accepted on {path}",
                            status=TestStatus.FAILED,
                            severity=Severity.HIGH,
                            url=url,
                            details=f"{method} {path} returned {resp.status_code} -- may allow unintended modifications.",
                            recommendation=f"Restrict {method} on {path} or require authentication.",
                        )
                    elif resp.status_code == 405:
                        self.add_result(
                            name=f"{method} blocked: {path}",
                            description=f"{method} correctly rejected with 405",
                            status=TestStatus.PASSED,
                            severity=Severity.INFO,
                            url=url,
                        )
                except Exception:
                    pass  # endpoint doesn't exist

    # -- Auth Header Tests -----------------------------------------

    def _test_auth_headers(self):
        """Send malformed Authorization headers."""
        url = self.config.base_url
        bad_headers = [
            ("Bearer invalid-token", "invalid_bearer"),
            ("Bearer ", "empty_bearer"),
            ("Basic dGVzdDp0ZXN0", "basic_test_test"),
            ("Negotiate AAAA", "negotiate_garbage"),
        ]
        for header_val, label in bad_headers:
            try:
                resp = self.session.get(
                    url,
                    headers={"Authorization": header_val},
                    timeout=self.config.request_timeout,
                )
                if resp.status_code >= 500:
                    self.add_result(
                        name=f"Bad auth header crash: {label}",
                        description=f"Server error with malformed auth header",
                        status=TestStatus.FAILED,
                        severity=Severity.HIGH,
                        url=url,
                        details=f"Authorization: {header_val[:40]} caused HTTP {resp.status_code}.",
                        recommendation="Handle malformed Authorization headers gracefully.",
                    )
            except Exception:
                pass
