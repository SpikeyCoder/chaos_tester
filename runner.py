"""
Chaos Tester — Test Runner

Orchestrates all test modules in sequence, collects results,
and produces a TestRun object.
"""

import time
import logging
from datetime import datetime
from typing import List, Optional

from .config import ChaosConfig
from .models import TestRun, TestResult
from .modules.availability import AvailabilityScanner
from .modules.links import BrokenLinkScanner
from .modules.forms import FormInteractionTester
from .modules.chaos import ChaosInjector
from .modules.auth import AuthTester
from .modules.security import SecurityScanner

logger = logging.getLogger("chaos_tester")


class ChaosTestRunner:
    """
    Main orchestrator.  Call .run() to execute a full test sweep.
    """

    def __init__(self, config: ChaosConfig):
        self.config = config.validate()
        self.test_run: Optional[TestRun] = None
        self._progress_callback = None

    def on_progress(self, callback):
        """Register a callback: callback(module_name, pct, message)"""
        self._progress_callback = callback

    def _emit(self, module: str, pct: int, msg: str):
        if self._progress_callback:
            self._progress_callback(module, pct, msg)
        logger.info(f"[{module}] ({pct}%) {msg}")

    def run(self) -> TestRun:
        """Execute the full test sweep and return a TestRun."""
        self.test_run = TestRun(
            base_url=self.config.base_url,
            environment=self.config.environment,
            status="running",
        )
        t0 = time.perf_counter()

        try:
            discovered_pages = []

            # ── Phase 1: Availability + Discovery ─────────────────
            if self.config.run_availability:
                self._emit("availability", 5, "Scanning pages and checking availability...")
                scanner = AvailabilityScanner(self.config)
                results = scanner.run()
                self.test_run.results.extend(results)
                # Extract successfully loaded pages for downstream modules
                discovered_pages = list({
                    r.url for r in results
                    if r.module == "availability" and "Page load" in r.name and r.status.value == "passed"
                })
                self._emit("availability", 20, f"Done — {len(discovered_pages)} pages OK, {len(results)} checks.")

            # ── Phase 2: Broken Links ─────────────────────────────
            if self.config.run_links:
                self._emit("links", 25, "Checking links, images, scripts, stylesheets...")
                link_scanner = BrokenLinkScanner(self.config)
                results = link_scanner.run(discovered_pages)
                self.test_run.results.extend(results)
                self._emit("links", 40, f"Done — {len(results)} resources checked.")

            # ── Phase 3: Forms & Interactions ─────────────────────
            if self.config.run_forms:
                self._emit("forms", 45, "Testing forms, buttons, and input handling...")
                form_tester = FormInteractionTester(self.config)
                results = form_tester.run(discovered_pages)
                self.test_run.results.extend(results)
                self._emit("forms", 55, f"Done — {len(results)} interaction tests.")

            # ── Phase 4: Chaos / Failure Injection ────────────────
            if self.config.run_chaos:
                self._emit("chaos", 60, "Running chaos / failure injection scenarios...")
                chaos = ChaosInjector(self.config)
                results = chaos.run(discovered_pages)
                self.test_run.results.extend(results)
                self._emit("chaos", 72, f"Done — {len(results)} chaos tests.")

            # ── Phase 5: Auth & Session ───────────────────────────
            if self.config.run_auth:
                self._emit("auth", 75, "Testing authentication and authorization...")
                auth_tester = AuthTester(self.config)
                results = auth_tester.run(discovered_pages)
                self.test_run.results.extend(results)
                self._emit("auth", 85, f"Done — {len(results)} auth tests.")

            # ── Phase 6: Security ─────────────────────────────────
            if self.config.run_security:
                self._emit("security", 88, "Running security scans...")
                sec = SecurityScanner(self.config)
                results = sec.run(discovered_pages)
                self.test_run.results.extend(results)
                self._emit("security", 97, f"Done — {len(results)} security checks.")

            self.test_run.status = "completed"

        except Exception as e:
            logger.exception("Test run failed: %s", e)
            self.test_run.status = "failed"
            # Sanitize the error message — strip tracebacks from
            # user-facing output while keeping the type + summary.
            err_type = type(e).__name__
            err_msg = str(e)[:200]  # truncate overly verbose messages
            self.test_run.results.append(TestResult(
                module="runner",
                name="Runner error",
                description=f"{err_type}: {err_msg}",
                status="error",
                severity="critical",
            ))

        elapsed = time.perf_counter() - t0
        self.test_run.duration_s = elapsed
        self.test_run.finished_at = datetime.utcnow().isoformat()
        self._emit("runner", 100, f"Complete — {len(self.test_run.results)} total checks in {elapsed:.1f}s")

        return self.test_run
