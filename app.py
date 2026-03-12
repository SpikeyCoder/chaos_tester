"""
Chaos Tester — Flask Web Application

Provides:
  • Admin dashboard to configure and launch test runs
  • Real-time progress via SSE (Server-Sent Events)
  • Report viewer for past runs
  • JSON API for programmatic access
"""

import os
import io
import csv
import json
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify, Response,
    redirect, url_for, send_from_directory, make_response,
)

from .config import ChaosConfig
from .runner import ChaosTestRunner
from .models import TestRun

# ── Setup ─────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = os.urandom(24)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger("chaos_tester")

# In-memory state
_current_run = None          # TestRun | None
_current_status = "idle"     # idle | running | completed | failed
_progress = []               # list of {module, pct, msg, ts}
_run_history = []             # list of saved TestRun dicts
_lock = threading.Lock()

# Load existing reports on startup
for f in sorted(REPORTS_DIR.glob("*.json")):
    try:
        data = json.loads(f.read_text())
        _run_history.append(data)
    except Exception:
        pass


# ── SSE Progress Stream ──────────────────────────────────────────

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
        for e in events:
            yield f"data: {json.dumps(e)}\n\n"
            idx += 1
        if status in ("completed", "failed", "idle") and idx >= len(_progress):
            yield f"data: {json.dumps({'module': 'done', 'pct': 100, 'msg': status})}\n\n"
            break
        time.sleep(0.5)


# ── Background Runner ────────────────────────────────────────────

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
        logger.exception(f"Run failed: {e}")
        test_run = runner.test_run or TestRun(status="failed")

    with _lock:
        _current_run = test_run
        _current_status = test_run.status

    # Save report
    report_data = test_run.to_dict()
    report_file = REPORTS_DIR / f"run_{test_run.run_id}.json"
    report_file.write_text(json.dumps(report_data, indent=2))
    _run_history.append(report_data)

    logger.info(f"Report saved: {report_file}")


# ── Routes ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html",
                           status=_current_status,
                           history=list(reversed(_run_history[-20:])))


@app.route("/run", methods=["POST"])
def start_run():
    global _current_status
    if _current_status == "running":
        return jsonify({"error": "A test run is already in progress."}), 409

    # Build config from form
    config = ChaosConfig(
        base_url=request.form.get("base_url", "http://localhost:8000").strip(),
        environment=request.form.get("environment", "staging"),
        allow_production=request.form.get("allow_production") == "on",
        max_pages=int(request.form.get("max_pages", 100)),
        crawl_depth=int(request.form.get("crawl_depth", 3)),
        request_timeout=int(request.form.get("request_timeout", 15)),
        run_availability=request.form.get("run_availability") == "on",
        run_links=request.form.get("run_links") == "on",
        run_forms=request.form.get("run_forms") == "on",
        run_chaos=request.form.get("run_chaos") == "on",
        run_auth=request.form.get("run_auth") == "on",
        run_security=request.form.get("run_security") == "on",
        chaos_intensity=request.form.get("chaos_intensity", "medium"),
        auth_url=request.form.get("auth_url", "").strip() or None,
        auth_cookie_name=request.form.get("auth_cookie_name", "sessionid").strip(),
        concurrency=int(request.form.get("concurrency", 5)),
    )

    # Seed URLs
    seeds = request.form.get("seed_urls", "").strip()
    if seeds:
        config.seed_urls = [s.strip() for s in seeds.split("\n") if s.strip()]

    try:
        config.validate()
    except (RuntimeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    thread = threading.Thread(target=_run_tests, args=(config,), daemon=True)
    thread.start()

    return redirect(url_for("progress_page"))


@app.route("/progress")
def progress_page():
    return render_template("progress.html", status=_current_status)


@app.route("/stream")
def stream():
    return Response(_event_stream(), mimetype="text/event-stream")


@app.route("/report/<run_id>")
def view_report(run_id):
    # Find in history
    for report in _run_history:
        if report.get("run_id") == run_id:
            return render_template("report.html", report=report)
    return "Report not found", 404


@app.route("/report/<run_id>/json")
def report_json(run_id):
    """View report as JSON in browser (API-style)."""
    for report in _run_history:
        if report.get("run_id") == run_id:
            return jsonify(report)
    return jsonify({"error": "Not found"}), 404


@app.route("/report/<run_id>/download/json")
def report_download_json(run_id):
    """Download report as a .json file."""
    for report in _run_history:
        if report.get("run_id") == run_id:
            payload = json.dumps(report, indent=2)
            resp = make_response(payload)
            resp.headers["Content-Type"] = "application/json"
            resp.headers["Content-Disposition"] = f'attachment; filename="chaos_report_{run_id}.json"'
            return resp
    return jsonify({"error": "Not found"}), 404


@app.route("/report/<run_id>/download/csv")
def report_download_csv(run_id):
    """Download report results as a .csv file."""
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
            resp.headers["Content-Disposition"] = f'attachment; filename="chaos_report_{run_id}.csv"'
            return resp
    return jsonify({"error": "Not found"}), 404


@app.route("/latest")
def latest_report():
    if _current_run:
        return redirect(url_for("view_report", run_id=_current_run.run_id))
    if _run_history:
        return redirect(url_for("view_report", run_id=_run_history[-1]["run_id"]))
    return redirect(url_for("index"))


@app.route("/api/status")
def api_status():
    return jsonify({
        "status": _current_status,
        "progress": _progress[-1] if _progress else None,
        "current_run_id": _current_run.run_id if _current_run else None,
    })


@app.route("/api/runs")
def api_runs():
    return jsonify([{
        "run_id": r["run_id"],
        "base_url": r["base_url"],
        "environment": r["environment"],
        "started_at": r["started_at"],
        "status": r["status"],
        "summary": r.get("summary", {}),
    } for r in reversed(_run_history[-50:])])


# ── Entry Point ───────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chaos Tester — Admin Dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"\n🐵 Chaos Tester Dashboard running at http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
