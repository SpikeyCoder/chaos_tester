"""
Chaos Tester — Configuration
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChaosConfig:
    """Central configuration for a Chaos Tester run."""

    # ── Target ────────────────────────────────────────────────────────
    base_url: str = "http://localhost:8000"
    environment: str = "staging"            # staging | test | production
    allow_production: bool = False          # explicit opt-in required

    # ── Crawl / Discovery ─────────────────────────────────────────────
    max_pages: int = 100                    # max pages to crawl
    crawl_depth: int = 3                    # link-follow depth
    respect_robots: bool = True
    excluded_paths: list = field(default_factory=lambda: [
        "/admin", "/api/internal", "/healthcheck",
    ])
    seed_urls: list = field(default_factory=list)  # additional start URLs

    # ── Timeouts ──────────────────────────────────────────────────────
    request_timeout: int = 15               # seconds per request
    page_load_timeout: int = 30             # seconds for full page load
    global_timeout: int = 600               # max total run time (10 min)

    # ── Auth ──────────────────────────────────────────────────────────
    auth_url: Optional[str] = None          # login endpoint
    auth_payload: dict = field(default_factory=dict)   # {"username": …, "password": …}
    auth_cookie_name: str = "sessionid"
    auth_header: Optional[str] = None       # "Bearer <token>" style

    # ── Test toggles ──────────────────────────────────────────────────
    run_availability: bool = True
    run_links: bool = True
    run_forms: bool = True
    run_chaos: bool = True
    run_auth: bool = True
    run_security: bool = True

    # ── Chaos / Fault-injection ───────────────────────────────────────
    chaos_targets: list = field(default_factory=lambda: [
        "api_latency", "api_error_500", "api_timeout",
        "missing_assets", "corrupted_cookies",
    ])
    chaos_intensity: str = "medium"         # low | medium | high

    # ── Reporting ─────────────────────────────────────────────────────
    report_dir: str = "reports"
    screenshots_dir: str = "screenshots"
    capture_screenshots: bool = True
    report_format: str = "html"             # html | json

    # ── Misc ──────────────────────────────────────────────────────────
    concurrency: int = 5
    user_agent: str = "ChaosMonkeyTester/1.0 (internal-qa)"
    verbose: bool = False

    def validate(self):
        """Safety gate — refuse to hit production unless explicitly allowed."""
        if self.environment == "production" and not self.allow_production:
            raise RuntimeError(
                "🛑 SAFETY: Production testing is disabled. "
                "Set allow_production=True AND environment='production' to override."
            )
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base_url: {self.base_url}")
        return self
