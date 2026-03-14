"""
Chaos Tester -- Test Runner

Orchestrates all test modules with concurrent execution:
  - Phase 1 (availability) runs first to discover pages
  - Phase 2 runs all remaining modules concurrently:
    links, forms, chaos, auth, security, performance, AI visibility
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from .modules.performance import fetch_performance_metrics
from .modules.ai_visibility import AIVisibilityScanner

logger = logging.getLogger("chaos_tester")


class ChaosTestRunner:
    """
    Main orchestrator.  Call .run() to execute a full test sweep.
    Uses concurrent execution for independent modules.
    """

    def __init__(self, config: ChaosConfig):
        self.config = config.validate()
        self.test_run: Optional[TestRun] = None
        self._progress_callback = None
        self._results_lock = threading.Lock()

    def on_progress(self, callback):
        """Register a callback: callback(module_name, pct, message)"""
        self._progress_callback = callback

    def _emit(self, module: str, pct: int, msg: str):
        if self._progress_callback:
            self._progress_callback(module, pct, msg)
        logger.info(f"[{module}] ({pct}%) {msg}")

    def _add_results(self, results):
        """Thread-safe result collection."""
        with self._results_lock:
            self.test_run.results.extend(results)

    # ── Module runners (each returns results list) ──────────────

    def _run_links(self, discovered_pages):
        self._emit("links", 25, "Checking links, images, scripts, stylesheets...")
        scanner = BrokenLinkScanner(self.config)
        results = scanner.run(discovered_pages)
        self._add_results(results)
        self._emit("links", 40, f"Done -- {len(results)} resources checked.")

    def _run_forms(self, discovered_pages):
        self._emit("forms", 45, "Testing forms, buttons, and input handling...")
        tester = FormInteractionTester(self.config)
        results = tester.run(discovered_pages)
        self._add_results(results)
        self._emit("forms", 55, f"Done -- {len(results)} interaction tests.")

    def _run_chaos(self, discovered_pages):
        self._emit("chaos", 60, "Running chaos / failure injection scenarios...")
        chaos = ChaosInjector(self.config)
        results = chaos.run(discovered_pages)
        self._add_results(results)
        self._emit("chaos", 72, f"Done -- {len(results)} chaos tests.")

    def _run_auth(self, discovered_pages):
        self._emit("auth", 75, "Testing authentication and authorization...")
        tester = AuthTester(self.config)
        results = tester.run(discovered_pages)
        self._add_results(results)
        self._emit("auth", 85, f"Done -- {len(results)} auth tests.")

    def _run_security(self, discovered_pages):
        self._emit("security", 88, "Running security scans...")
        scanner = SecurityScanner(self.config)
        results = scanner.run(discovered_pages)
        self._add_results(results)
        self._emit("security", 97, f"Done -- {len(results)} security checks.")

    def _run_performance(self):
        self._emit("performance", 50, "Fetching Lighthouse metrics...")
        try:
            perf = fetch_performance_metrics(self.config.base_url)
            self.test_run.performance_metrics = perf
            has_data = any(
                perf.get(s, {}).get("score") is not None
                for s in ("mobile", "desktop")
            )
            if has_data:
                self._emit("performance", 90, "Done -- performance metrics collected.")
            else:
                logger.warning("PSI returned empty data for %s", self.config.base_url)
                self._emit("performance", 90, "Performance data empty (API may be rate-limited).")
        except Exception as exc:
            logger.warning("Performance metrics failed: %s", exc)
            self._emit("performance", 90, "Performance metrics unavailable.")

    def _run_ai_visibility(self):
        self._emit("ai_visibility", 50, "Analyzing AI visibility...")
        try:
            ai_scanner = AIVisibilityScanner(self.config)
            ai_scanner.run()
            self._add_results(ai_scanner.results)
            self.test_run.ai_visibility = ai_scanner.ai_results
            self._emit("ai_visibility", 95, "Done -- AI visibility analysis complete.")
        except Exception as exc:
            logger.warning("AI visibility analysis failed: %s", exc)
            self._emit("ai_visibility", 95, "AI visibility analysis unavailable.")

    # ── Main entry point ────────────────────────────────────────

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

            # -- Phase 1: Availability + Discovery (must run first) --
            if self.config.run_availability:
                self._emit("availability", 5, "Scanning pages and checking availability...")
                scanner = AvailabilityScanner(self.config)
                results = scanner.run()
                self.test_run.results.extend(results)
                discovered_pages = list({
                    r.url for r in results
                    if r.module == "availability" and "Page load" in r.name and r.status.value == "passed"
                })
                self._emit("availability", 20, f"Done -- {len(discovered_pages)} pages OK, {len(results)} checks.")

            # -- Phase 2: All remaining modules concurrently ----------
            tasks = []

            if self.config.run_links:
                tasks.append(("links", lambda dp=discovered_pages: self._run_links(dp)))
            if self.config.run_forms:
                tasks.append(("forms", lambda dp=discovered_pages: self._run_forms(dp)))
            if self.config.run_chaos:
                tasks.append(("chaos", lambda dp=discovered_pages: self._run_chaos(dp)))
            if self.config.run_auth:
                tasks.append(("auth", lambda dp=discovered_pages: self._run_auth(dp)))
            if self.config.run_security:
                tasks.append(("security", lambda dp=discovered_pages: self._run_security(dp)))

            # Performance and AI visibility are always concurrent
            tasks.append(("performance", self._run_performance))
            if self.config.run_ai_visibility:
                tasks.append(("ai_visibility", self._run_ai_visibility))

            if tasks:
                self._emit("runner", 25, f"Running {len(tasks)} modules concurrently...")
                with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                    futures = {}
                    for name, fn in tasks:
                        futures[executor.submit(fn)] = name

                    for future in as_completed(futures):
                        name = futures[future]
                        try:
                            future.result()
                        except Exception as exc:
                            logger.warning("Module %s failed: %s", name, exc)
                            self._emit(name, 99, f"Module error: {exc}")

            self.test_run.status = "completed"

        except Exception as e:
            logger.exception("Test run failed: %s", e)
            self.test_run.status = "failed"
            err_type = type(e).__name__
            err_msg = str(e)[:200]
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
        self._emit("runner", 100, f"Complete -- {len(self.test_run.results)} total checks in {elapsed:.1f}s")

        return self.test_run
