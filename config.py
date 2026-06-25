from __future__ import annotations

"""
Chaos Tester -- Configuration
"""

import ipaddress
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("chaos_tester.config")


# Cloud metadata endpoints (GCP, AWS IMDSv1/v2, Azure, Oracle, Aliyun, etc.)
# plus their IPv6 forms. Matched both literally on the host string AND on
# every resolved IP — see _is_private_or_reserved() below.
#
# Pen-test 2026-06-10 finding WA-2026-06-10-01: the previous string-match
# was bypassed when an attacker-controlled hostname resolved (or was
# DNS-rebound) to one of these literals — `100.100.100.200`, for example,
# is not flagged by Python's `is_private`/`is_reserved` checks, so the
# Aliyun IMDS address would slip through unless we compared the resolved
# IP against the set as well.
_BLOCKED_METADATA_HOSTS: frozenset[str] = frozenset({
    "metadata.google.internal",
    "169.254.169.254",
    "metadata",
    "fd00:ec2::254",
    "100.100.100.200",
    # IPv4-mapped IPv6 form of the AWS/GCP IMDS — Python reports
    # is_private=True so the addr check catches it, but include the
    # literal here for defense-in-depth.
    "::ffff:169.254.169.254",
})

# IP-literal metadata endpoints, parsed once. Resolved IPs are compared
# against this set in _is_private_or_reserved() so the cloud-IMDS block
# is enforced by IP, not by hostname string.
_BLOCKED_METADATA_IPS: frozenset[ipaddress._BaseAddress] = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("100.100.100.200"),   # Aliyun ECS IMDS
        ipaddress.ip_address("fd00:ec2::254"),     # AWS IMDSv2 IPv6
        ipaddress.ip_address("::ffff:169.254.169.254"),
    }
)

# Additional networks that Python's stdlib does NOT flag as private/reserved
# but we want to refuse to fetch from. RFC 6598 carrier-grade NAT space
# (used by some VPN overlays such as Tailscale) is the most common gap.
# Pen-test 2026-06-10 finding WA-2026-06-10-02.
_BLOCKED_EXTRA_NETWORKS: tuple[ipaddress._BaseNetwork, ...] = (
    ipaddress.ip_network("100.64.0.0/10"),   # CGNAT (RFC 6598)
    ipaddress.ip_network("64:ff9b::/96"),    # NAT64 well-known prefix
    ipaddress.ip_network("64:ff9b:1::/48"),  # NAT64 local-use prefix
)


def _is_private_or_reserved(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private, loopback, or
    link-local address — or to a well-known cloud metadata endpoint
    (by literal hostname OR by resolved IP), or to a CGNAT / NAT64 range.

    Pen-test hardening 2026-06-10 (WA-2026-06-10-01 / WA-2026-06-10-02):
    Cloud-metadata blocking is now enforced on every resolved IP, not
    just the literal hostname string, and CGNAT (100.64.0.0/10) is
    explicitly blocked because `ipaddress.is_private` does not flag it.
    """
    if hostname.lower() in _BLOCKED_METADATA_HOSTS:
        return True
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canonname, sockaddr in infos:
            addr = ipaddress.ip_address(sockaddr[0])
            # Stdlib-known private / reserved space.
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return True
            # Cloud-metadata literals, matched by RESOLVED IP so an
            # attacker-controlled DNS record pointing to e.g.
            # 100.100.100.200 is also blocked.
            if addr in _BLOCKED_METADATA_IPS:
                return True
            # CGNAT (RFC 6598) and NAT64 — not flagged by stdlib but
            # commonly route to internal infrastructure.
            for net in _BLOCKED_EXTRA_NETWORKS:
                if addr.version == net.version and addr in net:
                    return True
    except (socket.gaierror, ValueError, OSError) as exc:
        # Fail CLOSED: if we cannot resolve / parse the address, refuse the
        # request rather than letting it through. A resolver quirk here could
        # differ from the connect-time resolver, and a security gate should
        # not default to "allow" when its check is inconclusive.
        logger.warning(
            "SSRF guard: blocking host %r because address check failed: %s",
            hostname, exc,
        )
        return True
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
    max_pages: int = 30                     # max pages to crawl (reduced for speed)
    crawl_depth: int = 2                    # link-follow depth (reduced for speed)
    respect_robots: bool = True
    excluded_paths: list = field(default_factory=lambda: [
        "/admin", "/api/internal", "/healthcheck",
    ])
    seed_urls: list = field(default_factory=list)  # additional start URLs

    # -- Timeouts ------------------------------------------------------
    request_timeout: int = 8                # seconds per request (reduced for speed)
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
    concurrency: int = 20
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
        self.concurrency = _clamp(self.concurrency, 1, 50)

        # Validate chaos intensity
        if self.chaos_intensity not in ("low", "medium", "high"):
            self.chaos_intensity = "medium"

        return self
