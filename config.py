"""
Chaos Tester -- Configuration
"""

import ipaddress
import os
import socket
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


def _is_private_or_reserved(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private, loopback, or
    link-local address -- or to a well-known cloud metadata endpoint.
    This provides SSRF protection by blocking requests to internal services."""
    BLOCKED_HOSTS = {"metadata.google.internal", "169.254.169.254"}
    if hostname.lower() in BLOCKED_HOSTS:
        return True
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canonname, sockaddr in infos:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return True
    except (socket.gaierror, ValueError, OSError):
        # DNS resolution failed -- allow the request (the HTTP client
        # will surface its own connection error later).
        pass
    return False


def _clamp(value: int, lo: int, hi: int) -> int:
    """Clamp *value* to the inclusive range [lo, hi]."""
    return max(lo, min(hi, value))


@dataclass
class ChaosConfig:
    """Central configuration for a Chaos Tester run."""

    # -- Target --------------------------------------------------------
    base_url: str = "http://localhost:8000"
    environment: str = "staging"            # staging | test | production
    allow_production: bool = False          # explicit opt-in required

    # -- Crawl / Discovery ---------------------------------------------
    max_pages: int = 100                    # max pages to crawl
    crawl_depth: int = 3                    # link-follow depth
    respect_robots: bool = True
    excluded_paths: list = field(default_factory=lambda: [
        "/admin", "/api/internal", "/healthcheck",
    ])
    seed_urls: list = field(default_factory=list)  # additional start URLs

    # -- Timeouts ------------------------------------------------------
    request_timeout: int = 15               # seconds per request
    page_load_timeout: int = 30             # seconds for full page load
    global_timeout: int = 600               # max total run time (10 min)

    # -- Auth ----------------------------------------------------------
    auth_url: Optional[str] = None          # login endpoint
    auth_payload: dict = field(default_factory=dict)   # {"username": …, "password": …}
    auth_cookie_name: str = "sessionid"
    auth_header: Optional[str] = None       # "Bearer <token>" style

    # -- Test toggles --------------------------------------------------
    run_availability: bool = True
    run_links: bool = True
    run_forms: bool = True
    run_chaos: bool = True
    run_auth: bool = True
    run_security: bool = True
    run_ai_visibility: bool = True
    business_location: str = ""           # optional user-provided city for AI queries
    perplexity_api_key: str = ""          # Perplexity API key for real AI visibility queries

    # -- Chaos / Fault-injection ---------------------------------------
    chaos_targets: list = field(default_factory=lambda: [
        "api_latency", "api_error_500", "api_timeout",
        "missing_assets", "corrupted_cookies",
    ])
    chaos_intensity: str = "medium"         # low | medium | high

    # -- Reporting -----------------------------------------------------
    report_dir: str = "reports"
    screenshots_dir: str = "screenshots"
    capture_screenshots: bool = True
    report_format: str = "html"             # html | json

    # -- Misc ----------------------------------------------------------
    concurrency: int = 5
    user_agent: str = "ChaosMonkeyTester/1.0 (internal-qa)"
    verbose: bool = False

    def validate(self):
        """Safety gate -- refuse to hit production unless explicitly allowed,
        validate URL format, block SSRF targets, and clamp numeric inputs."""
        # Production safety gate
        if self.environment == "production" and not self.allow_production:
            raise RuntimeError(
                "🛑 SAFETY: Production testing is disabled. "
                "Set allow_production=True AND environment='production' to override."
            )

        # Validate environment value
        if self.environment not in ("staging", "test", "production"):
            raise ValueError(
                f"Invalid environment: {self.environment!r} "
                "-- must be staging, test, or production."
            )

        # URL format check
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base_url: {self.base_url}")

        # SSRF protection -- block private/internal targets
        parsed = urlparse(self.base_url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Invalid base_url (no hostname): {self.base_url}")
        if _is_private_or_reserved(hostname):
            raise ValueError(
                f"SSRF protection: base_url resolves to a private or reserved "
                f"address ({hostname}). If you really need to test a local "
                "service, use its public hostname."
            )

        # Clamp numeric parameters to safe ranges
        self.max_pages = _clamp(self.max_pages, 1, 1000)
        self.crawl_depth = _clamp(self.crawl_depth, 1, 10)
        self.request_timeout = _clamp(self.request_timeout, 1, 120)
        self.concurrency = _clamp(self.concurrency, 1, 20)

        # Validate chaos intensity
        if self.chaos_intensity not in ("low", "medium", "high"):
            self.chaos_intensity = "medium"

        return self
