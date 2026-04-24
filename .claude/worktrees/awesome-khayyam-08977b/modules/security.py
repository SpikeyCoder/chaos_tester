"""
Module 6 -- Security Scanner

Checks for common security misconfigurations:
  - Missing security headers
  - Exposed server info / debug output
  - Directory listing enabled
  - Sensitive file exposure (.env, .git, etc.)
  - HTTPS enforcement
  - CORS misconfiguration
  - Content-Type sniffing
  - Clickjacking protection
"""

import logging
from typing import List
from urllib.parse import urljoin

from .base import BaseModule
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger("chaos_tester")


class SecurityScanner(BaseModule):

    MODULE_NAME = "security"

    # Files that should never be publicly accessible
    SENSITIVE_PATHS = [
        "/.env", "/.env.local", "/.env.production",
        "/.git/config", "/.git/HEAD",
        "/wp-config.php", "/config.php", "/settings.py",
        "/.htaccess", "/.htpasswd",
        "/server-status", "/server-info",
        "/phpinfo.php", "/info.php",
        "/debug", "/debug/vars", "/debug/pprof",
        "/.DS_Store", "/Thumbs.db",
        "/backup.sql", "/dump.sql", "/database.sql",
        "/robots.txt",  # not sensitive, but worth checking
        "/sitemap.xml",
        "/.well-known/security.txt",
        "/api/docs", "/swagger.json", "/openapi.json",
        "/graphql",
        "/elmah.axd", "/trace.axd",
    ]

    REQUIRED_HEADERS = {
        "X-Content-Type-Options": {
            "expected": "nosniff",
            "severity": Severity.MEDIUM,
            "recommendation": "Add 'X-Content-Type-Options: nosniff' to prevent MIME-type sniffing.",
        },
        "X-Frame-Options": {
            "expected": ["DENY", "SAMEORIGIN"],
            "severity": Severity.HIGH,
            "recommendation": "Add 'X-Frame-Options: DENY' or 'SAMEORIGIN' to prevent clickjacking.",
        },
        "X-XSS-Protection": {
            "expected": None,  # just check presence
            "severity": Severity.LOW,
            "recommendation": "Add 'X-XSS-Protection: 1; mode=block' (legacy but still useful).",
        },
        "Strict-Transport-Security": {
            "expected": None,
            "severity": Severity.HIGH,
            "recommendation": "Add 'Strict-Transport-Security: max-age=31536000; includeSubDomains' for HTTPS enforcement.",
        },
        "Content-Security-Policy": {
            "expected": None,
            "severity": Severity.MEDIUM,
            "recommendation": "Add a Content-Security-Policy header to mitigate XSS and injection attacks.",
        },
        "Referrer-Policy": {
            "expected": None,
            "severity": Severity.LOW,
            "recommendation": "Add 'Referrer-Policy: strict-origin-when-cross-origin' to control referrer leakage.",
        },
        "Permissions-Policy": {
            "expected": None,
            "severity": Severity.LOW,
            "recommendation": "Add a Permissions-Policy header to restrict browser feature access.",
        },
    }

    # Headers that leak server info
    INFO_LEAK_HEADERS = [
        "Server", "X-Powered-By", "X-AspNet-Version",
        "X-AspNetMvc-Version", "X-Runtime", "X-Debug-Token",
    ]

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        logger.info("[security] Running security checks concurrently")

        checks = [
            self._test_security_headers,
            self._test_info_leakage,
            self._test_sensitive_files,
            self._test_cors,
            self._test_https_enforcement,
            self._test_directory_listing,
            self._test_error_disclosure,
        ]

        with ThreadPoolExecutor(max_workers=len(checks)) as executor:
            futures = {executor.submit(fn): fn.__name__ for fn in checks}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.warning("Security check %s failed: %s", futures[future], exc)

        return self.results

    # -- Security Headers ------------------------------------------

    def _test_security_headers(self):
        url = self.config.base_url
        resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
        if not resp:
            return

        headers = resp.headers

        for header_name, spec in self.REQUIRED_HEADERS.items():
            value = headers.get(header_name)
            if not value:
                self.add_result(
                    name=f"Missing header: {header_name}",
                    description=f"Security header '{header_name}' not present",
                    status=TestStatus.WARNING,
                    severity=spec["severity"],
                    url=url,
                    details=f"Response is missing the '{header_name}' security header.",
                    recommendation=spec["recommendation"],
                )
            else:
                expected = spec["expected"]
                if expected:
                    if isinstance(expected, list):
                        ok = any(e.lower() in value.lower() for e in expected)
                    else:
                        ok = expected.lower() in value.lower()
                    if not ok:
                        self.add_result(
                            name=f"Weak header: {header_name}",
                            description=f"'{header_name}' value may be insufficient",
                            status=TestStatus.WARNING,
                            severity=Severity.LOW,
                            url=url,
                            details=f"Current value: '{value}'. Expected: {expected}.",
                            recommendation=spec["recommendation"],
                        )
                    else:
                        self.add_result(
                            name=f"Header OK: {header_name}",
                            description=f"'{header_name}: {value[:50]}'",
                            status=TestStatus.PASSED,
                            severity=Severity.INFO,
                            url=url,
                        )
                else:
                    self.add_result(
                        name=f"Header present: {header_name}",
                        description=f"'{header_name}: {value[:60]}'",
                        status=TestStatus.PASSED,
                        severity=Severity.INFO,
                        url=url,
                    )

    # -- Information Leakage ---------------------------------------

    def _test_info_leakage(self):
        url = self.config.base_url
        resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
        if not resp:
            return

        for header_name in self.INFO_LEAK_HEADERS:
            value = resp.headers.get(header_name)
            if value:
                self.add_result(
                    name=f"Info leak: {header_name}",
                    description=f"Server exposes '{header_name}: {value[:40]}'",
                    status=TestStatus.WARNING,
                    severity=Severity.MEDIUM,
                    url=url,
                    details=f"Header '{header_name}: {value}' reveals server technology.",
                    recommendation=f"Remove or obfuscate the '{header_name}' header in production.",
                )

    # -- Sensitive File Exposure -----------------------------------

    def _test_sensitive_files(self):
        base = self.config.base_url.rstrip("/")

        for path in self.SENSITIVE_PATHS:
            url = base + path
            resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
            if not resp:
                continue

            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "").lower()
                body_preview = resp.text[:200]

                # robots.txt and sitemap are expected to be public
                if path in ("/robots.txt", "/sitemap.xml", "/.well-known/security.txt"):
                    self.add_result(
                        name=f"Public file: {path}",
                        description=f"{path} is publicly accessible (expected)",
                        status=TestStatus.PASSED,
                        severity=Severity.INFO,
                        url=url,
                    )
                    continue

                # API docs might be intentional
                if path in ("/api/docs", "/swagger.json", "/openapi.json", "/graphql"):
                    self.add_result(
                        name=f"API docs exposed: {path}",
                        description=f"API documentation is publicly accessible",
                        status=TestStatus.WARNING,
                        severity=Severity.MEDIUM,
                        url=url,
                        details=f"{path} returned 200. May expose internal API structure.",
                        recommendation="Restrict API docs to authenticated users in production.",
                    )
                    continue

                # Everything else is a problem
                # Only truly critical: .env and .git exposure (active security risk)
                sev = Severity.CRITICAL if any(s in path for s in [".env", ".git"]) else Severity.HIGH
                self.add_result(
                    name=f"Sensitive file exposed: {path}",
                    description=f"⚠ '{path}' is publicly accessible!",
                    status=TestStatus.FAILED,
                    severity=sev,
                    url=url,
                    details=f"HTTP 200 for {path}. Content-Type: {content_type}. Preview: {body_preview[:80]}...",
                    recommendation=f"Block access to '{path}' via web server config. Never expose config or DB files.",
                    duration_ms=dt,
                )

    # -- CORS Misconfiguration -------------------------------------

    def _test_cors(self):
        url = self.config.base_url
        malicious_origins = [
            "https://evil.com",
            "https://attacker.example.com",
            "null",
        ]

        for origin in malicious_origins:
            resp, err, dt = self._safe_request(
                "get", url,
                headers={"Origin": origin},
                timeout=self.config.request_timeout,
            )
            if not resp:
                continue

            acao = resp.headers.get("Access-Control-Allow-Origin", "")
            acac = resp.headers.get("Access-Control-Allow-Credentials", "")

            if acao == "*":
                self.add_result(
                    name="CORS: wildcard origin",
                    description="Access-Control-Allow-Origin is set to '*'",
                    status=TestStatus.WARNING,
                    severity=Severity.MEDIUM,
                    url=url,
                    details="Wildcard CORS allows any website to make requests.",
                    recommendation="Restrict CORS to specific trusted origins.",
                )
                break
            elif origin in acao:
                sev = Severity.CRITICAL if acac.lower() == "true" else Severity.HIGH
                self.add_result(
                    name=f"CORS reflects origin: {origin}",
                    description="Server reflects arbitrary origin in CORS headers",
                    status=TestStatus.FAILED,
                    severity=sev,
                    url=url,
                    details=f"Origin '{origin}' was reflected. Credentials: {acac}.",
                    recommendation="Validate origins against an allowlist; never reflect arbitrary origins.",
                )
                break

        else:
            self.add_result(
                name="CORS: properly configured",
                description="Server does not reflect arbitrary origins",
                status=TestStatus.PASSED,
                severity=Severity.INFO,
                url=url,
            )

    # -- HTTPS Enforcement -----------------------------------------

    def _test_https_enforcement(self):
        url = self.config.base_url
        if url.startswith("https://"):
            http_url = url.replace("https://", "http://", 1)
            try:
                resp = self.session.get(http_url, timeout=self.config.request_timeout, allow_redirects=False)
                if 300 <= resp.status_code < 400:
                    location = resp.headers.get("Location", "")
                    if location.startswith("https://"):
                        self.add_result(
                            name="HTTP → HTTPS redirect",
                            description="HTTP correctly redirects to HTTPS",
                            status=TestStatus.PASSED,
                            severity=Severity.INFO,
                            url=http_url,
                        )
                    else:
                        self.add_result(
                            name="HTTP redirect (not HTTPS)",
                            description=f"HTTP redirects but not to HTTPS: {location}",
                            status=TestStatus.WARNING,
                            severity=Severity.MEDIUM,
                            url=http_url,
                            recommendation="Ensure HTTP redirects specifically to HTTPS.",
                        )
                elif resp.status_code == 200:
                    self.add_result(
                        name="HTTP accessible (no redirect)",
                        description="Site is accessible over plain HTTP without redirect",
                        status=TestStatus.FAILED,
                        severity=Severity.HIGH,
                        url=http_url,
                        details="HTTP requests are served directly without upgrading to HTTPS.",
                        recommendation="Add HTTP → HTTPS redirect and HSTS header.",
                    )
            except Exception:
                pass  # HTTP port may be closed, which is fine

    # -- Directory Listing -----------------------------------------

    def _test_directory_listing(self):
        base = self.config.base_url.rstrip("/")
        dirs_to_check = ["/static/", "/uploads/", "/images/", "/assets/", "/media/", "/files/"]

        for path in dirs_to_check:
            url = base + path
            resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
            if not resp or resp.status_code != 200:
                continue

            body = resp.text.lower()
            if "index of" in body or "directory listing" in body or "<pre>" in body:
                self.add_result(
                    name=f"Directory listing: {path}",
                    description=f"Directory listing enabled at {path}",
                    status=TestStatus.FAILED,
                    severity=Severity.HIGH,
                    url=url,
                    details="Server reveals directory contents -- attackers can enumerate files.",
                    recommendation="Disable directory listing in web server config (e.g., Options -Indexes).",
                    duration_ms=dt,
                )

    # -- Error Disclosure ------------------------------------------

    def _test_error_disclosure(self):
        """Trigger errors and check if stack traces or debug info leak."""
        base = self.config.base_url.rstrip("/")

        # Malformed requests likely to trigger errors
        payloads = [
            (base + "/%00", "null_byte"),
            (base + "/..%2f..%2fetc%2fpasswd", "path_traversal"),
            (base + "/?id=1'", "sql_injection_probe"),
            (base + "/<script>", "xss_in_url"),
        ]

        for url, label in payloads:
            resp, err, dt = self._safe_request("get", url, timeout=self.config.request_timeout)
            if not resp:
                continue

            body = resp.text[:5000].lower()
            stack_trace_indicators = [
                "traceback", "stack trace", "exception", "at line",
                "debug", "error in", "syntax error", "warning:",
                "mysql", "postgresql", "sqlite", "mongodb",
                "file \"", "line ", "module '",
            ]

            found = [ind for ind in stack_trace_indicators if ind in body]
            if found and resp.status_code >= 400:
                self.add_result(
                    name=f"Error disclosure: {label}",
                    description=f"Server leaks debug info on error ({label})",
                    status=TestStatus.FAILED,
                    severity=Severity.HIGH,
                    url=url,
                    details=f"Error response contains: {', '.join(found[:5])}",
                    recommendation="Disable debug mode in production. Use generic error pages.",
                    duration_ms=dt,
                )
