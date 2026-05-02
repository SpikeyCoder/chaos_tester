from __future__ import annotations

"""
Website Auditor -- Flask Web Application

Provides:
  - Admin dashboard to configure and launch test runs
  - Real-time progress via SSE (Server-Sent Events)
  - Report viewer for past runs
  - JSON API for programmatic access
"""

import hashlib
import hmac
import io
import csv
import json
import os
import re
import secrets
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify, Response,
    redirect, url_for, send_from_directory, make_response,
    abort, session, flash,
)

from .config import ChaosConfig
from .runner import ChaosTestRunner
from .models import TestRun
from . import supabase_client as supa
from . import wa_auth

# -- Setup ---------------------------------------------------------

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Secret key: prefer an environment variable; fall back to random bytes
# with a startup warning so operators know sessions won't survive restarts.
_secret = os.environ.get("CHAOS_TESTER_SECRET_KEY")
if not _secret:
    _secret = secrets.token_hex(32)
    logging.getLogger("chaos_tester").warning(
        "CHAOS_TESTER_SECRET_KEY not set -- using a random key. "
        "Sessions will not survive server restarts. "
        "Set the env var for persistence."
    )

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = _secret
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB request body limit (screenshots)
app.config["GOOGLE_PLACES_API_KEY"] = os.environ.get("GOOGLE_PLACES_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger("chaos_tester")

# In-memory state
_current_run = None          # TestRun | None
_current_status = "idle"     # idle | running | completed | failed
_progress = []               # list of {module, pct, msg, ts}
_highest_pct = 0             # monotonic high-water mark for progress percentage
_run_history = []             # list of saved TestRun dicts
_run_index = {}              # run_id -> report dict for O(1) lookup
_lock = threading.Lock()

# Load existing reports on startup
for f in sorted(REPORTS_DIR.glob("*.json")):
    try:
        data = json.loads(f.read_text())
        _run_history.append(data)
        _run_index[data["run_id"]] = data
    except Exception:
        pass


# -- Security Helpers ---------------------------------------------

_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_run_id(run_id: str) -> str:
    """Reject run_id values that could cause path traversal or injection."""
    if not _RUN_ID_RE.match(run_id):
        abort(400, "Invalid run ID.")
    return run_id


def _generate_csrf_token() -> str:
    """Create a per-session CSRF token."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def _validate_csrf_token():
    """Abort with 403 if the submitted CSRF token doesn't match the session."""
    token = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(token, expected):
        abort(403, "CSRF token missing or invalid.")


# Make csrf_token available in all templates
app.jinja_env.globals["csrf_token"] = _generate_csrf_token


@app.after_request
def _set_security_headers(response):
    """Attach security + CORS headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com https://gc.zgo.at https://maps.googleapis.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https://maps.googleapis.com https://maps.gstatic.com; "
        "connect-src 'self' https://website-auditor.io https://chaos-tester-878428558569.us-central1.run.app https://website-auditor.goatcounter.com https://maps.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com;"
    )
    # CORS headers for cross-origin SPA (GitHub Pages → backend).
    # The allowlist is read from CORS_ALLOWED_ORIGINS so production deploys
    # can ship without the localhost dev origin baked in. Default keeps
    # production behaviour for the public site if the env var is unset.
    origin = request.headers.get("Origin", "")
    allowed_env = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "https://website-auditor.io,https://spikeycoder.github.io",
    )
    allowed = [o.strip() for o in allowed_env.split(",") if o.strip()]
    if origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
    return response


@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def _cors_preflight(path):
    """Handle CORS preflight requests."""
    return "", 204


def _clamp_int(raw: str, default: int, lo: int, hi: int) -> int:
    """Parse a form value to int, clamping to [lo, hi]."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


# -- SSE Progress Stream ------------------------------------------

# Track per-module completion for accurate overall progress.
# Modules: availability, links, forms, chaos, auth, security, performance, ai_visibility
_ALL_MODULES = ["availability", "links", "forms", "chaos", "auth", "security", "performance", "ai_visibility"]
_module_done: set = set()
_total_modules: int = len(_ALL_MODULES)


def _progress_callback(module: str, pct: int, msg: str):
    global _progress, _highest_pct, _module_done, _total_modules

    # Track which modules have reported "Done"
    is_done = msg and (msg.lower().startswith("done") or "complete" in msg.lower())
    if is_done and module in _ALL_MODULES:
        _module_done.add(module)

    # Calculate overall progress from module completion ratio.
    # Reserve 0-5% for startup, 5-95% for modules, 95-100% for finalization.
    if module == "runner" and pct >= 100:
        effective_pct = 100
    elif module == "runner":
        effective_pct = max(5, _highest_pct)
    else:
        done_ratio = len(_module_done) / max(_total_modules, 1)
        effective_pct = int(5 + done_ratio * 90)
        # If a module is actively running but not done, show partial credit
        if module in _ALL_MODULES and module not in _module_done:
            # Give partial credit for active modules (half a module's share)
            partial = 0.5 / max(_total_modules, 1) * 90
            effective_pct = max(effective_pct, int(5 + (len(_module_done) * 90 / max(_total_modules, 1)) + partial))

    effective_pct = max(effective_pct, _highest_pct)
    _highest_pct = effective_pct
    entry = {"module": module, "pct": effective_pct, "msg": msg, "ts": datetime.utcnow().isoformat()}
    with _lock:
        _progress.append(entry)


def _event_stream():
    """Yield SSE events for the current run progress."""
    idx = 0
    while True:
        with _lock:
            events = _progress[idx:]
            status = _current_status
            run_id = _current_run.run_id if _current_run else None
        for e in events:
            yield f"data: {json.dumps(e)}\n\n"
            idx += 1
        if status in ("completed", "failed", "idle") and idx >= len(_progress):
            yield f"data: {json.dumps({'module': 'done', 'pct': 100, 'msg': status, 'run_id': run_id})}\n\n"
            break
        time.sleep(0.5)


# -- Background Runner --------------------------------------------

MAX_RETRIES = 3
RETRY_DELAY_SECS = 3


def _run_tests(config: ChaosConfig):
    global _current_run, _current_status, _progress

    # Note: _current_status is already set to "running" and _progress cleared
    # by the /run route before this thread starts (avoids race condition).

    test_run = None

    for attempt in range(1, MAX_RETRIES + 1):
        runner = ChaosTestRunner(config)
        runner.on_progress(_progress_callback)

        try:
            test_run = runner.run()
        except Exception as e:
            logger.exception("Run attempt %d/%d failed: %s", attempt, MAX_RETRIES, e)
            test_run = runner.test_run or TestRun(status="failed")

        # If the run succeeded (or at least completed), we're done
        if test_run and test_run.status == "completed":
            break

        # If we have retries left, reset and try again
        if attempt < MAX_RETRIES:
            logger.info("Retrying run (attempt %d/%d)...", attempt + 1, MAX_RETRIES)
            _progress_callback(
                "runner", 0,
                f"⚠️ Run issue detected -- automatically retrying (attempt {attempt + 1}/{MAX_RETRIES})..."
            )
            time.sleep(RETRY_DELAY_SECS)
            # Keep status as running so SSE stream doesn't close
            with _lock:
                _current_status = "running"
        else:
            logger.error("All %d retry attempts exhausted.", MAX_RETRIES)

    with _lock:
        _current_run = test_run
        _current_status = test_run.status

    # Save report
    report_data = test_run.to_dict()

    # Generate a content-addressable hash ID for persistent storage
    hash_id = supa.generate_report_id(
        report_data.get("base_url", ""),
        report_data.get("started_at", ""),
        len(report_data.get("results", [])),
    )
    report_data["hash_id"] = hash_id

    report_file = REPORTS_DIR / f"run_{test_run.run_id}.json"
    report_file.write_text(json.dumps(report_data, indent=2))

    with _lock:
        _run_history.append(report_data)
        _run_index[report_data["run_id"]] = report_data
        # Also index by hash_id so either ID resolves
        _run_index[hash_id] = report_data

    logger.info("Report saved locally: %s (hash_id: %s)", report_file, hash_id)

    # Persist to Supabase (fire-and-forget; local is primary)
    supa.save_report(report_data)


# -- Routes --------------------------------------------------------

@app.route("/")
def index():
    with _lock:
        status = _current_status
    return render_template("dashboard.html", status=status)


@app.route("/run", methods=["POST"])
def start_run():
    global _current_status

    is_json = request.is_json

    # CSRF: validate token for form POSTs; require X-Requested-With for JSON
    # (the custom header triggers a CORS preflight, which blocks cross-site CSRF)
    if is_json:
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            abort(403, "Missing X-Requested-With header.")
    else:
        _validate_csrf_token()

    with _lock:
        if _current_status == "running":
            return jsonify({"error": "A test run is already in progress."}), 409

    # Read from JSON body or form depending on content type
    if is_json:
        data = request.get_json(silent=True) or {}
        _get = lambda key, default="": data.get(key, default)  # noqa: E731
        _bool = lambda key: bool(data.get(key, False))  # noqa: E731
    else:
        _get = lambda key, default="": request.form.get(key, default)  # noqa: E731
        _bool = lambda key: request.form.get(key) == "on"  # noqa: E731

    # Normalize URL: auto-prepend https:// if no scheme is present.
    # The client JS does this too, but some mobile browsers don't propagate
    # the programmatic .value change into FormData for type="url" inputs.
    raw_url = _get("base_url", "http://localhost:8000").strip()
    if raw_url and not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    config = ChaosConfig(
        base_url=raw_url,
        environment=_get("environment", "staging"),
        allow_production=_bool("allow_production"),
        max_pages=_clamp_int(_get("max_pages"), 100, 1, 1000),
        crawl_depth=_clamp_int(_get("crawl_depth"), 3, 1, 10),
        request_timeout=_clamp_int(_get("request_timeout"), 8, 1, 120),
        run_availability=_bool("run_availability"),
        run_links=_bool("run_links"),
        run_forms=_bool("run_forms"),
        run_chaos=_bool("run_chaos"),
        run_auth=_bool("run_auth"),
        run_security=_bool("run_security"),
        chaos_intensity=_get("chaos_intensity", "medium"),
        auth_url=_get("auth_url", "").strip() or None,
        auth_cookie_name=_get("auth_cookie_name", "sessionid").strip(),
        concurrency=_clamp_int(_get("concurrency"), 5, 1, 20),
    )

    # Production mode validation: reject if environment=production and allow_production checkbox not checked
    if config.environment == "production" and not config.allow_production:
        return jsonify({"error": "Production mode requires opt-in. Check the 'I understand and want to test production' checkbox."}), 400

    # AI Visibility options
    config.business_location = _get("business_location", "").strip()
    config.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "")
    seeds = _get("seed_urls", "").strip()
    if seeds:
        config.seed_urls = [s.strip() for s in seeds.split("\n") if s.strip()]

    try:
        config.validate()
    except (RuntimeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    # Set status to "running" BEFORE starting thread to prevent race condition
    # where the SSE stream sees "idle" before the thread has a chance to run.
    with _lock:
        global _highest_pct, _module_done, _total_modules
        _current_status = "running"
        _progress.clear()
        _highest_pct = 0
        _module_done = set()
        # Count how many modules are actually enabled for this run
        _total_modules = sum([
            config.run_availability, config.run_links, config.run_forms,
            config.run_chaos, config.run_auth, config.run_security,
            True,  # performance always runs
            config.run_ai_visibility,
        ])

    thread = threading.Thread(target=_run_tests, args=(config,), daemon=True)
    thread.start()

    # JSON callers get a JSON response; form callers get a redirect
    if is_json:
        with _lock:
            run_id = _current_run.run_id if _current_run else None
        return jsonify({"status": "started", "run_id": run_id}), 202

    return redirect(url_for("progress_page"))


@app.route("/progress")
def progress_page():
    with _lock:
        status = _current_status
    return render_template("progress.html", status=status)


@app.route("/stream")
def stream():
    return Response(_event_stream(), mimetype="text/event-stream")


def _resolve_report(run_id: str) -> dict | None:
    """3-tier report lookup: memory → disk → Supabase."""
    with _lock:
        report = _run_index.get(run_id)
    if report:
        return report
    report_file = REPORTS_DIR / f"run_{run_id}.json"
    if report_file.exists():
        try:
            report = json.loads(report_file.read_text())
            with _lock:
                _run_index[run_id] = report
            return report
        except Exception:
            pass
    report = supa.load_report(run_id)
    if report:
        with _lock:
            _run_index[run_id] = report
        logger.info("Report %s loaded from Supabase", run_id)
    return report


@app.route("/report/<run_id>")
def view_report(run_id):
    _validate_run_id(run_id)
    report = _resolve_report(run_id)

    if not report:
        flash("Report not found. It may have expired or the link is invalid.", "warning")
        return redirect(url_for("index"))

    # Fetch domain history for the "Previous audits" panel
    domain = supa.normalize_domain(report.get("base_url", ""))
    domain_history = supa.get_domain_history(domain, limit=10)

    # Gate the AI Visibility custom-search widget behind an active
    # paid/trial subscription on api.website-auditor.io. None ⇒ show banner.
    entitlement = wa_auth.get_current_entitlement(request)

    # Build an absolute https return_to URL for the upsell banner. We can't
    # trust request.url here because the app runs behind a Cloud Run proxy
    # that rewrites Host to the *.run.app backend hostname. The Node-side
    # admin portal only accepts https://(www.)?website-auditor.io, so we
    # prefer X-Forwarded-Host and fall back to a hardcoded public host.
    forwarded_host = request.headers.get("X-Forwarded-Host", "").split(",")[0].strip()
    if forwarded_host and forwarded_host.endswith("website-auditor.io"):
        public_host = forwarded_host
    elif request.host.endswith("website-auditor.io"):
        public_host = request.host
    else:
        public_host = "website-auditor.io"
    return_to_url = f"https://{public_host}{request.full_path.rstrip('?')}"

    return render_template(
        "report.html",
        report=report,
        domain_history=domain_history,
        domain=domain,
        ai_query_entitled=entitlement is not None,
        return_to_url=return_to_url,
    )


@app.route("/report/<run_id>/json")
def report_json(run_id):
    """View report as JSON in browser (API-style)."""
    _validate_run_id(run_id)
    report = _resolve_report(run_id)
    if report:
        return jsonify(report)
    return jsonify({"error": "Not found"}), 404


@app.route("/report/<run_id>/download/json")
def report_download_json(run_id):
    """Download report as a .json file."""
    _validate_run_id(run_id)
    report = _resolve_report(run_id)
    if report:
        payload = json.dumps(report, indent=2)
        resp = make_response(payload)
        resp.headers["Content-Type"] = "application/json"
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="audit_report_{run_id}.json"'
        )
        return resp
    return jsonify({"error": "Not found"}), 404


@app.route("/report/<run_id>/download/csv")
def report_download_csv(run_id):
    """Download report results as a .csv file."""
    _validate_run_id(run_id)
    report = _resolve_report(run_id)
    if report:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "test_id", "module", "status", "severity", "name",
            "description", "url", "details", "recommendation",
            "duration_ms", "timestamp",
        ])

        for r in report.get("results", []):
            writer.writerow([
                r.get("test_id", ""),
                r.get("module", ""),
                r.get("status", ""),
                r.get("severity", ""),
                r.get("name", ""),
                r.get("description", ""),
                r.get("url", ""),
                r.get("details", ""),
                r.get("recommendation", ""),
                r.get("duration_ms", 0),
                r.get("timestamp", ""),
            ])

        resp = make_response(output.getvalue())
        resp.headers["Content-Type"] = "text/csv"
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="audit_report_{run_id}.csv"'
        )
        return resp
    return jsonify({"error": "Not found"}), 404


@app.route("/latest")
def latest_report():
    with _lock:
        if _current_run:
            run_id = _current_run.run_id
            return redirect(url_for("view_report", run_id=run_id))
        if _run_history:
            run_id = _run_history[-1]["run_id"]
            return redirect(url_for("view_report", run_id=run_id))
    flash("No reports yet — run your first audit!", "warning")
    return redirect(url_for("index"))


@app.route("/api/domain-history/<path:domain>")
def api_domain_history(domain):
    """Get audit history for a domain (rate-limited, validated)."""
    # Validate domain format to prevent injection
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain):
        return jsonify({"error": "Invalid domain format"}), 400
    history = supa.get_domain_history(domain, limit=10)
    return jsonify(history)


@app.route("/api/status")
def api_status():
    with _lock:
        return jsonify({
            "status": _current_status,
            "progress": _progress[-1] if _progress else None,
            "current_run_id": _current_run.run_id if _current_run else None,
        })


@app.route("/api/runs")
def api_runs():
    # Require X-Requested-With to prevent cross-origin abuse
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        abort(403, "Missing X-Requested-With header.")
    with _lock:
        runs = [{
            "run_id": r["run_id"],
            "base_url": r["base_url"],
            "environment": r["environment"],
            "started_at": r["started_at"],
            "status": r["status"],
            "summary": r.get("summary", {}),
        } for r in reversed(_run_history[-50:])]
    return jsonify(runs)




@app.route("/api/ai-query", methods=["POST"])
def api_ai_query():
    """Run a custom AI visibility query against all platforms."""
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        abort(403, "Missing X-Requested-With header.")

    # Gate: require an active paid or trialing subscription at
    # api.website-auditor.io. Verified via the wa_auth cookie set by
    # the admin portal after successful Google / magic-link auth.
    if not wa_auth.is_entitled(request):
        return jsonify({
            "error": "subscription_required",
            "message": "An active API subscription or free trial is required to run custom AI visibility queries.",
            "upgrade_url": "https://api.website-auditor.io/admin_portal/",
        }), 403

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    run_id = (data.get("run_id") or "").strip()

    if not query:
        return jsonify({"error": "query is required"}), 400
    if len(query) > 300:
        return jsonify({"error": "query too long (max 300 chars)"}), 400

    # Get business info from the report (if available)
    business_name = ""
    with _lock:
        report = _run_index.get(run_id, {}) if run_id else {}
    ai_data = report.get("ai_visibility", {})
    business_info = ai_data.get("business_info", {})
    business_name = business_info.get("business_name", "")

    # Run query against all AI platforms via Perplexity
    from .modules.ai_visibility import AI_PLATFORMS, AIVisibilityScanner

    api_key = os.getenv("PERPLEXITY_API_KEY", "")
    results = []

    for platform_info in AI_PLATFORMS:
        platform_name = platform_info["name"]

        # Use the scanner's query method
        if api_key:
            import requests as http_requests
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful local business advisor. "
                            "List the top 5 businesses that match the query. "
                            "For each business, include the business name. "
                            "Format as a numbered list."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "max_tokens": 400,
                "temperature": 0.1,
            }
            try:
                resp = http_requests.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers, json=payload, timeout=25,
                )
                if resp.status_code == 200:
                    content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    # Parse business names
                    names = []
                    for line in content.split("\n"):
                        line = line.strip()
                        m = re.match(r"^(?:\d+[\.\)]\s*|\-\s*|\*\s*)", line)
                        if m:
                            rest = line[m.end():]
                            bold = re.match(r"\*\*(.+?)\*\*", rest)
                            name = bold.group(1).strip() if bold else re.match(r"(.+?)(?:\s*[\-–:(\[,]|$)", rest)
                            if isinstance(name, re.Match):
                                name = name.group(1).strip()
                            name = re.sub(r"\s*\[\d+\]", "", str(name)).strip().rstrip("*").strip()
                            if 3 <= len(name) <= 80:
                                names.append(name)

                    # Check if business appears
                    client_appears = False
                    position = 0
                    if business_name:
                        bn_lower = business_name.lower()
                        for idx, n in enumerate(names):
                            if bn_lower in n.lower() or n.lower() in bn_lower:
                                client_appears = True
                                position = idx + 1
                                break

                    results.append({
                        "platform": platform_name,
                        "platform_logo_url": platform_info["logo_url"],
                        "platform_color": platform_info["color"],
                        "query": query,
                        "recommended": ", ".join(names[:5]),
                        "client_appears": client_appears,
                        "position": position,
                    })
                else:
                    results.append({
                        "platform": platform_name,
                        "platform_logo_url": platform_info["logo_url"],
                        "platform_color": platform_info["color"],
                        "query": query,
                        "recommended": "(API error)",
                        "client_appears": False,
                        "position": 0,
                    })
            except Exception as exc:
                logger.warning("Custom AI query failed for %s: %s", platform_name, exc)
                results.append({
                    "platform": platform_name,
                    "platform_logo_url": platform_info["logo_url"],
                    "platform_color": platform_info["color"],
                    "query": query,
                    "recommended": "(query failed)",
                    "client_appears": False,
                    "position": 0,
                })
        else:
            # No API key configured: return error instead of fake data
            return jsonify({
                "error": "No PERPLEXITY_API_KEY configured. Set this environment variable to enable real AI visibility queries.",
                "requires_api_key": True
            }), 503

    return jsonify({"query": query, "results": results})


@app.route("/api/bug-report", methods=["POST"])
def api_bug_report():
    """Create a Trello card from a bug report or feature request."""
    import requests as http_requests
    import base64

    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        abort(403, "Missing X-Requested-With header.")

    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()
    is_feature = bool(data.get("isFeatureRequest", False))
    screenshot_data = data.get("screenshotData")  # base64 data URL or null
    tech_ctx = data.get("technicalContext", {})

    if not description:
        return jsonify({"error": "Description is required"}), 400
    if len(description) > 2000:
        return jsonify({"error": "Description too long (max 2000 chars)"}), 400

    # -- Trello credentials --
    trello_key = os.getenv("TRELLO_API_KEY", "")
    trello_token = os.getenv("TRELLO_TOKEN", "")
    trello_list = os.getenv("TRELLO_LIST_ID", "")

    if not trello_key or not trello_token or not trello_list:
        logger.error("Missing Trello configuration — check env vars")
        return jsonify({"error": "Server configuration error"}), 500

    # -- Build card --
    prefix = "[FEATURE REQUEST]" if is_feature else "[BUG]"
    title_text = description[:60]
    card_name = f"{prefix} {title_text}{'...' if len(description) > 60 else ''}"

    lines = [description, "", "---", "📋 **Technical Context**"]
    lines.append(f"- **Source:** Website Auditor")
    lines.append(f"- **URL:** {tech_ctx.get('url', 'N/A')}")
    lines.append(f"- **Page:** {tech_ctx.get('pageName', 'N/A')}")
    lines.append(f"- **Device:** {tech_ctx.get('deviceType', 'N/A')}")
    lines.append(f"- **Browser / OS:** {tech_ctx.get('userAgent', 'N/A')}")
    lines.append(f"- **Platform:** {tech_ctx.get('platform', 'N/A')}")
    lines.append(f"- **Viewport:** {tech_ctx.get('viewportSize', 'N/A')}")
    lines.append(f"- **Screen:** {tech_ctx.get('screenSize', 'N/A')}")
    lines.append(f"- **Timestamp:** {tech_ctx.get('timestamp', 'N/A')}")

    recent_errors = tech_ctx.get("recentErrors", [])
    if recent_errors:
        lines.append("")
        lines.append("⚠️ **Recent Console Errors**")
        for err in recent_errors[:5]:
            lines.append(f"- {err}")

    card_desc = "\n".join(lines)

    # -- Create Trello card --
    try:
        card_resp = http_requests.post(
            "https://api.trello.com/1/cards",
            params={
                "key": trello_key,
                "token": trello_token,
                "idList": trello_list,
                "name": card_name,
                "desc": card_desc,
                "pos": "top",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if not card_resp.ok:
            logger.error("Trello card creation failed: %s %s", card_resp.status_code, card_resp.text)
            return jsonify({"error": "Failed to create report card"}), 502

        card = card_resp.json()
        card_id = card.get("id", "")

        # -- Attach screenshot if provided --
        if screenshot_data and card_id:
            try:
                # Strip data URL prefix: "data:image/png;base64,..."
                if "," in screenshot_data:
                    screenshot_data = screenshot_data.split(",", 1)[1]
                img_bytes = base64.b64decode(screenshot_data)

                attach_resp = http_requests.post(
                    f"https://api.trello.com/1/cards/{card_id}/attachments",
                    params={"key": trello_key, "token": trello_token},
                    files={"file": ("screenshot.png", img_bytes, "image/png")},
                    timeout=20,
                )
                if not attach_resp.ok:
                    logger.warning("Screenshot attachment failed: %s", attach_resp.status_code)
            except Exception as exc:
                logger.warning("Screenshot attachment error: %s", exc)

        return jsonify({"ok": True, "cardId": card_id})

    except http_requests.exceptions.Timeout:
        return jsonify({"error": "Trello API timed out"}), 504
    except Exception as exc:
        logger.exception("Bug report error: %s", exc)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/detect-business", methods=["POST"])
def detect_business():
    """Quick-detect business name, location, and sector from a URL.

    SECURITY: this endpoint accepts a user-supplied URL and fetches it
    server-side. To prevent Server-Side Request Forgery (CWE-918,
    OWASP A10:2021) we:

    1.  Require an ``X-Requested-With: XMLHttpRequest`` header so the
        endpoint cannot be triggered cross-origin without a CORS preflight
        (consistent with /api/ai-query and /api/bug-report).
    2.  Reject non-``http(s)`` schemes outright.
    3.  Validate the hostname via ``_is_private_or_reserved`` BEFORE any
        outbound request, blocking loopback, link-local, RFC1918, reserved,
        and known cloud-metadata addresses.
    4.  Use ``SafeSession`` for the actual fetch so the same hostname check
        is re-applied on every redirect hop (DNS-rebinding defence).
    """
    from urllib.parse import urlparse
    from .modules.business_identifier import BusinessIdentifier
    from .config import _is_private_or_reserved
    from .safe_http import SafeSession, SSRFBlockedError

    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        abort(403, "Missing X-Requested-With header.")

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return jsonify({"error": "Only http(s) URLs are supported."}), 400
    hostname = (parsed.hostname or "").strip()
    if not hostname:
        return jsonify({"error": "URL is missing a hostname."}), 400
    if _is_private_or_reserved(hostname):
        logger.warning("detect-business SSRF blocked: %s", hostname)
        return jsonify({"error": "URL refers to a private or reserved address."}), 400

    try:
        sess = SafeSession()
        sess.headers["User-Agent"] = "ChaosMonkeyTester/1.0 (business-detect)"
        identifier = BusinessIdentifier(session=sess, timeout=10)
        result = identifier.identify(url)
        return jsonify({
            "business_name": result.get("business_name", ""),
            "location": result.get("location", ""),
            "sector": result.get("sector", "local business services"),
            "lookup_source": result.get("lookup_source", ""),
            "candidates": result.get("candidates", [])[:5],
        })
    except SSRFBlockedError as exc:
        logger.warning("detect-business SSRF blocked at fetch time: %s", exc)
        return jsonify({"error": "URL refers to a private or reserved address."}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "business_name": "", "location": "", "sector": ""}), 200


# -- Error Handlers -----------------------------------------------

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(405)
def method_not_allowed(e):
    # Return 404 for GET requests to unknown paths (prevents 405 for missing pages)
    if request.method == "GET":
        return render_template("404.html"), 404
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_server_error(e):
    logger.exception("Internal server error")
    return render_template("500.html"), 500


# Protected Paths (return 404 instead of 405)
_PROTECTED = {
    "/account","/admin","/api/admin","/api/private",
    "/api/settings","/api/users","/billing","/config",
    "/dashboard","/internal","/manage","/orders",
    "/payments","/profile","/settings","/users",
}

@app.before_request
def _block_protected():
    if request.path in _PROTECTED:
        abort(404)

# -- Entry Point ---------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Website Auditor -- Admin Dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logger.warning(
            "Running in DEBUG mode -- do not use in production. "
            "Debug mode exposes a debugger and auto-reloads."
        )

    print(f"\n🐵 Website Auditor Dashboard running at http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)




# -- SEO Routes ------------------------------------------------
@app.route("/robots.txt")
def robots_txt():
    content = """User-agent: *
Allow: /
Disallow: /run
Disallow: /api/
Disallow: /report/

Sitemap: https://website-auditor.io/sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    pages = [
        {"loc": "https://website-auditor.io/", "priority": "1.0", "changefreq": "weekly", "lastmod": today},
        {"loc": "https://website-auditor.io/features", "priority": "0.8", "changefreq": "monthly", "lastmod": "2026-03-14"},
        {"loc": "https://website-auditor.io/how-it-works", "priority": "0.8", "changefreq": "monthly", "lastmod": "2026-03-14"},
        {"loc": "https://website-auditor.io/sample-report", "priority": "0.7", "changefreq": "monthly", "lastmod": "2026-03-14"},
        {"loc": "https://website-auditor.io/latest", "priority": "0.6", "changefreq": "daily", "lastmod": today},
        {"loc": "https://website-auditor.io/api", "priority": "0.7", "changefreq": "monthly", "lastmod": today},
        {"loc": "https://website-auditor.io/about", "priority": "0.5", "changefreq": "monthly", "lastmod": today},
        {"loc": "https://website-auditor.io/contact", "priority": "0.5", "changefreq": "monthly", "lastmod": today},
        {"loc": "https://website-auditor.io/privacy", "priority": "0.4", "changefreq": "yearly", "lastmod": today},
        {"loc": "https://website-auditor.io/terms", "priority": "0.4", "changefreq": "yearly", "lastmod": today},
        {"loc": "https://website-auditor.io/changelog", "priority": "0.5", "changefreq": "monthly", "lastmod": today},
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for p in pages:
        xml += f'  <url>\n'
        xml += f'    <loc>{p["loc"]}</loc>\n'
        xml += f'    <lastmod>{p["lastmod"]}</lastmod>\n'
        xml += f'    <changefreq>{p["changefreq"]}</changefreq>\n'
        xml += f'    <priority>{p["priority"]}</priority>\n'
        xml += f'  </url>\n'
    xml += '</urlset>'
    return Response(xml, mimetype="application/xml")


@app.route("/features")
def features_page():
    return render_template("features.html")


@app.route("/how-it-works")
def how_it_works_page():
    return render_template("how_it_works.html")


@app.route("/sample-report")
def sample_report_page():
    return render_template("sample_report.html")


@app.route("/api")
def api_docs_page():
    return render_template("api_docs.html")


@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/contact")
def contact_page():
    return render_template("contact.html")


@app.route("/privacy")
def privacy_page():
    return render_template("privacy.html")


@app.route("/terms")
def terms_page():
    return render_template("terms.html")


@app.route("/status")
def status_page():
    return render_template("status.html")


@app.route("/changelog")
def changelog_page():
    return render_template("changelog.html")


if __name__ == "__main__":
    main()
