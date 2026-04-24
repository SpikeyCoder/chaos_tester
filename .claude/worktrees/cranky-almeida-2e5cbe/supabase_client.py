"""
Supabase integration for persistent report storage.

Reports are stored with content-addressable IDs (SHA-256 hash of
domain + timestamp + results count). This provides:
  - Permanent, shareable URLs: /report/{hash_id}
  - Domain-based history: all audits for a domain, newest first
  - No auth required: anyone with the link can view
  - 90-day TTL with automatic cleanup
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import requests

logger = logging.getLogger("chaos_tester.supabase")

# -- Configuration ----------------------------------------------------

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://psunubqeuopyzgjdytrn.supabase.co"
)
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBzdW51YnFldW9weXpnamR5dHJuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ3NDk1MzMsImV4cCI6MjA5MDMyNTUzM30.Gh_INivkDi_8MdkWd8SCdrRTCAaQGXGV9epjf-Fk9Pg",
)

_REST_URL = f"{SUPABASE_URL}/rest/v1"


def _is_configured() -> bool:
    """Return True if Supabase service key is available for writes."""
    return bool(SUPABASE_SERVICE_KEY)


def _read_headers() -> dict:
    """Headers for anonymous (public) reads."""
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }


def _write_headers() -> dict:
    """Headers for service-role writes."""
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


# -- Helpers -----------------------------------------------------------

def normalize_domain(url: str) -> str:
    """Extract and normalize the domain from a URL."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    domain = (parsed.hostname or "").lower()
    # Strip leading "www."
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def generate_report_id(base_url: str, started_at: str, results_count: int) -> str:
    """
    Generate a content-addressable report ID.

    Hash is deterministic: same URL + timestamp + result count = same ID.
    First 12 chars of SHA-256 hex digest (matches existing run_id length).
    """
    content = f"{base_url}|{started_at}|{results_count}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]


# -- Write (server-side, requires service key) -------------------------

def save_report(report_data: dict) -> str | None:
    """
    Save a report to Supabase. Returns the content-hash ID, or None on failure.

    This is a fire-and-forget operation — local storage is the primary,
    Supabase is the persistent backup for link sharing and domain history.
    """
    if not _is_configured():
        logger.warning("SUPABASE_SERVICE_KEY not set — skipping remote save")
        return None

    try:
        base_url = report_data.get("base_url", "")
        started_at = report_data.get("started_at", "")
        results = report_data.get("results", [])
        summary = report_data.get("summary", {})

        report_id = generate_report_id(base_url, started_at, len(results))
        domain = normalize_domain(base_url)

        row = {
            "id": report_id,
            "domain": domain,
            "base_url": base_url,
            "started_at": started_at,
            "finished_at": report_data.get("finished_at"),
            "duration_s": report_data.get("duration_s"),
            "status": report_data.get("status", "completed"),
            "overall_score": summary.get("pass_rate"),
            "total_tests": summary.get("total"),
            "passed": summary.get("passed"),
            "failed": summary.get("failed"),
            "warnings": summary.get("warnings"),
            "errors": summary.get("errors"),
            "report_json": report_data,
        }

        resp = requests.post(
            f"{_REST_URL}/reports",
            headers={**_write_headers(), "Prefer": "return=minimal,resolution=merge-duplicates"},
            json=row,
            timeout=10,
        )

        if resp.status_code in (200, 201, 204):
            logger.info("Report %s saved to Supabase (domain: %s)", report_id, domain)
            return report_id
        else:
            logger.error(
                "Supabase save failed (%d): %s", resp.status_code, resp.text[:200]
            )
            return None

    except Exception:
        logger.exception("Failed to save report to Supabase")
        return None


# -- Read (anonymous, no service key needed) ---------------------------

def load_report(report_id: str) -> dict | None:
    """Load a single report by its content-hash ID from Supabase."""
    try:
        resp = requests.get(
            f"{_REST_URL}/reports",
            headers=_read_headers(),
            params={
                "id": f"eq.{report_id}",
                "select": "report_json",
                "limit": "1",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                return rows[0]["report_json"]
        return None
    except Exception:
        logger.exception("Failed to load report %s from Supabase", report_id)
        return None


def get_active_subscription(user_id: str) -> dict | None:
    """
    Return the user's currently-entitled subscription row, or None.

    A user is considered entitled when they have a row in the
    ``subscriptions`` table with ``status`` in ``('active', 'trialing')``.
    Uses the service-role key because the main site queries on behalf of
    a user identified only by the ``wa_auth`` cookie (no per-user Supabase
    session is established here).

    Returns the row dict on hit, or None on miss/error.
    """
    if not user_id:
        return None
    if not _is_configured():
        logger.warning("SUPABASE_SERVICE_KEY not set — cannot check subscription")
        return None
    try:
        resp = requests.get(
            f"{_REST_URL}/subscriptions",
            headers=_write_headers(),
            params={
                "user_id": f"eq.{user_id}",
                "status": "in.(active,trialing)",
                "select": "status,current_period_end,trial_end",
                "limit": "1",
            },
            timeout=5,
        )
        if resp.status_code == 200:
            rows = resp.json()
            return rows[0] if rows else None
        logger.error(
            "Supabase subscription lookup failed (%d): %s",
            resp.status_code,
            resp.text[:200],
        )
        return None
    except Exception:
        logger.exception("Failed to look up subscription for user %s", user_id)
        return None


def get_domain_history(domain: str, limit: int = 10) -> list[dict]:
    """
    Get recent audit history for a domain.

    Returns a list of summary dicts (no full report_json) sorted newest first.
    """
    try:
        resp = requests.get(
            f"{_REST_URL}/reports",
            headers=_read_headers(),
            params={
                "domain": f"eq.{domain}",
                "select": "id,domain,base_url,started_at,finished_at,duration_s,status,overall_score,total_tests,passed,failed,warnings,errors",
                "order": "started_at.desc",
                "limit": str(limit),
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        logger.exception("Failed to load domain history for %s", domain)
        return []
