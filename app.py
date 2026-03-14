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
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB request body limit

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger("chaos_tester")

# In-memory state
_current_run = None          # TestRun | None
_current_status = "idle"     # idle | running | completed | failed
_progress = []               # list of {module, pct, msg, ts}
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
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' https://website-auditor.io https://chaos-tester-878428558569.us-central1.run.app;"
    )
    # CORS headers for cross-origin SPA (GitHub Pages → localhost backend)
    origin = request.headers.get("Origin", "")
    allowed = ["https://website-auditor.io", "https://spikeycoder.github.io", "http://localhost:5000"]
    if origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
    response.headers["Server"] = "WebAuditor"
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

def _progress_callback(module: str, pct: int, msg: str):
    global _progress
    entry = {"module": module, "pct": pct, "msg": msg, "ts": datetime.utcnow().isoformat()}
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

def _run_tests(config: ChaosConfig):
    global _current_run, _current_status, _progress

    with _lock:
        _current_status = "running"
        _progress = []

    runner = ChaosTestRunner(config)
    runner.on_progress(_progress_callback)

    try:
        test_run = runner.run()
    except Exception as e:
        logger.exception("Run failed: %s", e)
        test_run = runner.test_run or TestRun(status="failed")

    with _lock:
        _current_run = test_run
        _current_status = test_run.status

    # Save report
    report_data = test_run.to_dict()
    report_file = REPORTS_DIR / f"run_{test_run.run_id}.json"
    report_file.write_text(json.dumps(report_data, indent=2))

    with _lock:
        _run_history.append(report_data)
        _run_index[report_data["run_id"]] = report_data

    logger.info("Report saved: %s", report_file)


# -- Routes --------------------------------------------------------

@app.route("/")
def index():
    with _lock:
        status = _current_status
        history = list(reversed(_run_history[-20:]))
    return render_template("dashboard.html", status=status, history=history)


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

    config = ChaosConfig(
        base_url=_get("base_url", "http://localhost:8000").strip(),
        environment=_get("environment", "staging"),
        allow_production=_bool("allow_production"),
        max_pages=_clamp_int(_get("max_pages"), 100, 1, 1000),
        crawl_depth=_clamp_int(_get("crawl_depth"), 3, 1, 10),
        request_timeout=_clamp_int(_get("request_timeout"), 15, 1, 120),
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

    # Seed URLs
    config.business_location = _get("business_location", "").strip()
    seeds = _get("seed_urls", "").strip()
    if seeds:
        config.seed_urls = [s.strip() for s in seeds.split("\n") if s.strip()]

    try:
        import sys; print(f"[DEBUG /run] env={config.environment}, allow_prod={config.allow_production}, is_json={is_json}", file=sys.stderr)
        config.validate()
    except (RuntimeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

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


@app.route("/report/<run_id>")
def view_report(run_id):
    _validate_run_id(run_id)
    with _lock:
        report = _run_index.get(run_id)
    if report:
        return render_template("report.html", report=report)
    # Fallback: try loading from disk (handles container restarts / new instances)
    report_file = REPORTS_DIR / f"run_{run_id}.json"
    if report_file.exists():
        try:
            data = json.loads(report_file.read_text())
            with _lock:
                _run_index[run_id] = data
            return render_template("report.html", report=data)
        except Exception:
            pass
    # No report found anywhere - redirect to dashboard instead of 404
    flash("Report not found. It may have been cleared or has not been generated yet.", "warning")
    return redirect(url_for("index"))


@app.route("/report/<run_id>/json")
def report_json(run_id):
    """View report as JSON in browser (API-style)."""
    _validate_run_id(run_id)
    with _lock:
        for report in _run_history:
            if report.get("run_id") == run_id:
                return jsonify(report)
    return jsonify({"error": "Not found"}), 404


@app.route("/report/<run_id>/download/json")
def report_download_json(run_id):
    """Download report as a .json file."""
    _validate_run_id(run_id)
    with _lock:
        for report in _run_history:
            if report.get("run_id") == run_id:
                payload = json.dumps(report, indent=2)
                resp = make_response(payload)
                resp.headers["Content-Type"] = "application/json"
                resp.headers["Content-Disposition"] = (
                    f'attachment; filename="chaos_report_{run_id}.json"'
                )
                return resp
    return jsonify({"error": "Not found"}), 404


@app.route("/report/<run_id>/download/csv")
def report_download_csv(run_id):
    """Download report results as a .csv file."""
    _validate_run_id(run_id)
    with _lock:
        for report in _run_history:
            if report.get("run_id") == run_id:
                output = io.StringIO()
                writer = csv.writer(output)

                # Header row
                writer.writerow([
                    "test_id", "module", "status", "severity", "name",
                    "description", "url", "details", "recommendation",
                    "duration_ms", "timestamp",
                ])

                # Data rows
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
                    f'attachment; filename="chaos_report_{run_id}.csv"'
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
    return redirect(url_for("index"))


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
    pages = [
        {"loc": "https://website-auditor.io/", "priority": "1.0", "changefreq": "weekly"},
        {"loc": "https://website-auditor.io/features", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "https://website-auditor.io/how-it-works", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "https://website-auditor.io/latest", "priority": "0.6", "changefreq": "daily"},
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for p in pages:
        xml += f'  <url>\n'
        xml += f'    <loc>{p["loc"]}</loc>\n'
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


if __name__ == "__main__":
    main()
