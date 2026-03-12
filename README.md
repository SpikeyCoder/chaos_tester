# 🐵 Chaos Tester

An internal Chaos-Monkey-inspired web testing tool that runs a full automated resilience, QA, and security sweep across any website in a single execution. Point it at a URL, click one button, and get a detailed report covering page availability, broken links, form handling, failure injection, authentication enforcement, and security misconfigurations.

## Table of Contents

- [Quick Start](#quick-start)
- [Hosted Dashboard (GitHub Pages)](#hosted-dashboard-github-pages)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Web Dashboard](#web-dashboard)
  - [Command-Line Options](#command-line-options)
  - [Python API](#python-api)
  - [REST API](#rest-api)
- [Test Modules](#test-modules)
- [Configuration Reference](#configuration-reference)
- [Reports](#reports)
- [Safety & Production Guardrails](#safety--production-guardrails)
- [CI/CD Integration](#cicd-integration)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Quick Start

```bash
git clone https://github.com/your-org/chaos-tester.git
cd chaos-tester
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5000** in your browser. Enter your staging URL, select the test modules you want, and click **Launch Chaos Test**.

## Hosted Dashboard (GitHub Pages)

The Chaos Tester dashboard is available as a hosted static SPA at:

**https://spikeycoder.github.io/chaos_tester/**

This frontend communicates with your locally running backend — no server deployment required.

### How it works

1. **Start the backend locally:**
   ```bash
   cd chaos_tester
   python run.py
   ```
2. **Open the hosted dashboard** at the URL above (or open `frontend/index.html` locally)
3. **Configure the backend URL** — click **Settings** in the nav bar and enter your backend address (default: `http://localhost:5000`). Click **Test Connection** to verify.
4. **Run tests** — use the dashboard exactly as you would the localhost version

The frontend auto-deploys to GitHub Pages on every push to `main` that changes files in the `frontend/` directory. The deployment is handled by the GitHub Actions workflow in `.github/workflows/deploy-pages.yml`.

### Architecture

The project uses a split architecture:

- **Frontend (GitHub Pages):** A single-file SPA (`frontend/index.html`) with all UI logic in vanilla HTML/CSS/JS. No build step required.
- **Backend (local):** The Flask server handles test execution, SSE progress streaming, report storage, and JSON/CSV downloads. CORS headers allow the remote frontend to communicate with the local backend.

## Requirements

- Python 3.9 or later
- pip

The tool has three dependencies (all installed via `requirements.txt`):

| Package | Purpose |
|---|---|
| `flask` | Web dashboard and API server |
| `requests` | HTTP client for all test requests |
| `beautifulsoup4` | HTML parsing for crawling, form discovery, and link extraction |

## Installation

### Option A: Install from requirements.txt

```bash
pip install -r requirements.txt
```

### Option B: Install packages directly

```bash
pip install flask requests beautifulsoup4
```

### Option C: Use a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

## Usage

### Web Dashboard

The primary way to use Chaos Tester. Start the dashboard server:

```bash
python run.py
```

This opens an admin interface at `http://127.0.0.1:5000` where you can:

1. **Configure the target** — enter the base URL for your staging or test environment
2. **Select modules** — toggle individual test suites on or off (availability, links, forms, chaos, auth, security)
3. **Set intensity** — choose low, medium, or high for the chaos/failure injection module
4. **Launch** — click the button and watch real-time progress via server-sent events
5. **View reports** — browse the full filterable report when done, or review past runs from the history table

### Command-Line Options

```bash
python run.py --host 127.0.0.1 --port 5000        # defaults
python run.py --host 0.0.0.0 --port 8080           # listen on all interfaces, custom port
python run.py --debug                                # Flask debug mode (auto-reload)
```

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address for the Flask server |
| `--port` | `5000` | Port number |
| `--debug` | off | Enable Flask debug mode with auto-reload |

### Python API

Use Chaos Tester as a library in your own scripts or test suites:

```python
from chaos_tester import ChaosConfig, ChaosTestRunner

# Configure the run
config = ChaosConfig(
    base_url="https://staging.example.com",
    environment="staging",
    max_pages=50,
    crawl_depth=3,
    chaos_intensity="medium",
    run_availability=True,
    run_links=True,
    run_forms=True,
    run_chaos=True,
    run_auth=True,
    run_security=True,
)

# Execute
runner = ChaosTestRunner(config)
result = runner.run()

# Inspect results
print(f"Status: {result.status}")
print(f"Total tests: {result.summary['total']}")
print(f"Pass rate: {result.summary['pass_rate']}%")

# List failures
for r in result.failed:
    print(f"  [{r.severity.value}] {r.name}")
    print(f"    Details: {r.details}")
    print(f"    Fix: {r.recommendation}")

# Export to JSON
import json
with open("report.json", "w") as f:
    json.dump(result.to_dict(), f, indent=2)
```

You can also attach a progress callback to monitor execution:

```python
def on_progress(module, pct, message):
    print(f"  [{module}] {pct}% — {message}")

runner = ChaosTestRunner(config)
runner.on_progress(on_progress)
result = runner.run()
```

### REST API

The dashboard exposes a JSON API for programmatic access and CI/CD integration:

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Current run status (`idle`, `running`, `completed`, `failed`) and progress |
| `/api/runs` | GET | List of all past runs with summaries |
| `/report/<run_id>/json` | GET | Full JSON report for a specific run |
| `/run` | POST | Start a new test run (accepts form-encoded or JSON body) |
| `/stream` | GET | Server-sent event stream for real-time progress |

**Example: Start a run via curl**

```bash
curl -X POST http://127.0.0.1:5000/run \
  -d "base_url=https://staging.example.com" \
  -d "environment=staging" \
  -d "max_pages=50" \
  -d "run_availability=on" \
  -d "run_links=on" \
  -d "run_forms=on" \
  -d "run_chaos=on" \
  -d "run_auth=on" \
  -d "run_security=on" \
  -d "chaos_intensity=medium"
```

**Example: Poll for completion**

```bash
curl http://127.0.0.1:5000/api/status
# {"status": "running", "progress": {"module": "security", "pct": 88, "msg": "..."}}
```

**Example: Retrieve the report**

```bash
curl http://127.0.0.1:5000/api/runs           # find the run_id
curl http://127.0.0.1:5000/report/abc123/json  # get full report
```

## Test Modules

### 🌐 Availability Scanner
Crawls from the base URL using BFS, discovers internal pages up to the configured depth, and checks each one for HTTP status codes, response time thresholds (3s warning / 8s failure), and error text embedded in HTML bodies (stack traces, "internal server error", etc.).

### 🔗 Broken Link Scanner
Extracts all `<a>`, `<img>`, `<script>`, and `<link>` resources across every discovered page and verifies each one resolves with a HEAD request. Uses concurrent workers for speed.

### 📝 Form Interaction Tester
Finds all `<form>` elements and tests them for: CSRF token presence on POST forms, server response to empty submissions, reflected XSS payloads in response bodies, and `required` attribute enforcement. Also flags standalone buttons outside forms.

### 🐵 Chaos / Failure Injector
Simulates failure scenarios including: aggressive timeout probes to find latency-sensitive pages, error page quality checks (custom vs. generic 404/500), missing asset handling, and corrupted cookie resilience. Intensity levels (low/medium/high) control how aggressive the probes are.

### 🔒 Auth & Session Tester
Probes common protected paths (`/admin`, `/dashboard`, `/settings`, `/api/users`, etc.) without authentication to verify they return 401/403 or redirect to login. Checks cookie security flags (Secure, HttpOnly, SameSite). Tests session manipulation with tampered, empty, and garbage session tokens. Verifies dangerous HTTP methods (DELETE, PUT, PATCH) are blocked on sensitive endpoints.

### 🛡 Security Scanner
Checks for 7 security headers (CSP, HSTS, X-Frame-Options, etc.), scans 30+ sensitive file paths (`.env`, `.git/config`, `backup.sql`, `phpinfo.php`, etc.), tests CORS configuration with malicious origins, verifies HTTP-to-HTTPS redirect, checks for directory listing, and probes for error disclosure via malformed requests.

## Configuration Reference

All options are set via the `ChaosConfig` dataclass (Python API) or the web dashboard form:

| Parameter | Default | Description |
|---|---|---|
| `base_url` | `http://localhost:8000` | Target website URL |
| `environment` | `staging` | `staging`, `test`, or `production` |
| `allow_production` | `False` | Must be `True` to test production |
| `max_pages` | `100` | Maximum pages to crawl |
| `crawl_depth` | `3` | How many link-hops deep to follow |
| `request_timeout` | `15` | Seconds before a request times out |
| `concurrency` | `5` | Parallel workers for link checking |
| `chaos_intensity` | `medium` | `low`, `medium`, or `high` |
| `auth_url` | `None` | Login page URL (optional) |
| `auth_cookie_name` | `sessionid` | Name of the session cookie to test |
| `auth_header` | `None` | `Authorization` header value (e.g., `Bearer <token>`) |
| `seed_urls` | `[]` | Extra starting URLs beyond the base |
| `excluded_paths` | `["/admin", ...]` | Paths to skip during crawl |
| `run_availability` | `True` | Enable/disable each module |
| `run_links` | `True` | |
| `run_forms` | `True` | |
| `run_chaos` | `True` | |
| `run_auth` | `True` | |
| `run_security` | `True` | |

## Reports

Each completed run generates a JSON report saved in the `reports/` directory. Reports include:

- **Summary stats** — total tests, passed, failed, warnings, errors, and pass rate
- **Per-module breakdown** — pass/fail/warning counts for each of the 6 modules
- **Detailed results** — every individual test with status, severity level (critical/high/medium/low/info), affected URL, details, timing, and a recommended fix
- **Filtering** — the web dashboard lets you filter by status (passed/failed/warning) and by module
- **JSON export** — download the raw JSON for processing in external tools

### Severity Levels

| Level | Meaning | Example |
|---|---|---|
| **Critical** | Immediate action required | Server crash on empty form, sensitive file exposed, unprotected admin route |
| **High** | Significant issue | Missing HSTS header, reflected XSS, broken internal links |
| **Medium** | Should be addressed | Slow response times, info-leaking headers, generic error pages |
| **Low** | Minor improvement | Missing Referrer-Policy, no `required` attributes on forms |
| **Info** | Passed / informational | Successful checks, confirmed good behavior |

## Safety & Production Guardrails

Chaos Tester is designed as an internal tool that runs against **staging or test environments** by default:

- **Production is blocked.** If `environment` is set to `production`, the tool refuses to run unless `allow_production` is explicitly set to `True`. The web dashboard shows a warning banner and requires a confirmation checkbox.
- **Read-only by default.** The tool primarily uses GET and HEAD requests. POST requests are limited to form testing with obviously non-destructive payloads (empty strings, XSS markers, special characters).
- **No data mutation.** The tool never creates, updates, or deletes data on the target. It only reads and probes.
- **No credential storage.** Auth tokens and cookies are held in memory for the duration of a single run and never persisted.

## CI/CD Integration

You can integrate Chaos Tester into your deployment pipeline by using the Python API and failing the build on a low pass rate:

```python
import sys
from chaos_tester import ChaosConfig, ChaosTestRunner

config = ChaosConfig(
    base_url="https://staging.example.com",
    environment="staging",
    max_pages=50,
)

result = ChaosTestRunner(config).run()
rate = result.summary["pass_rate"]
criticals = [r for r in result.failed if r.severity.value == "critical"]

print(f"Pass rate: {rate}%  |  Critical failures: {len(criticals)}")

if criticals:
    print("BLOCKING: Critical failures found:")
    for r in criticals:
        print(f"  - {r.name}: {r.details}")
    sys.exit(1)

if rate < 80:
    print(f"BLOCKING: Pass rate {rate}% is below 80% threshold")
    sys.exit(1)

print("All checks passed.")
```

Or use the REST API with curl in a shell script:

```bash
# Start the run
curl -s -X POST http://127.0.0.1:5000/run -d "base_url=$STAGING_URL&environment=staging&run_availability=on&run_security=on"

# Wait and poll
sleep 30
STATUS=$(curl -s http://127.0.0.1:5000/api/status | jq -r '.status')
while [ "$STATUS" = "running" ]; do sleep 5; STATUS=$(curl -s http://127.0.0.1:5000/api/status | jq -r '.status'); done

# Check results
RATE=$(curl -s http://127.0.0.1:5000/api/runs | jq '.[0].summary.pass_rate')
echo "Pass rate: $RATE%"
```

## Project Structure

```
chaos_tester/
├── run.py                 # Entry point — start here
├── app.py                 # Flask web application (dashboard, API, SSE)
├── config.py              # ChaosConfig dataclass with all options
├── models.py              # TestResult / TestRun data models
├── runner.py              # Orchestrator that runs all modules in sequence
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Python packaging config
├── LICENSE                # MIT License
├── README.md              # This file
├── frontend/
│   └── index.html         # Static SPA dashboard (deployed to GitHub Pages)
├── .github/
│   └── workflows/
│       └── deploy-pages.yml  # Auto-deploy frontend to GitHub Pages
├── modules/
│   ├── __init__.py        # Module exports
│   ├── base.py            # BaseModule with shared HTTP helpers
│   ├── availability.py    # Page crawler + availability checker
│   ├── links.py           # Broken link / resource scanner
│   ├── forms.py           # Form interaction + CSRF + XSS tester
│   ├── chaos.py           # Failure injection scenarios
│   ├── auth.py            # Auth, session, and permission tester
│   └── security.py        # Security header + misconfiguration scanner
├── templates/
│   ├── base.html          # Shared layout, CSS, navigation
│   ├── dashboard.html     # Configuration form + run history
│   ├── progress.html      # Real-time progress via SSE
│   └── report.html        # Full report with filters and stats
├── reports/               # Auto-generated JSON reports
└── static/                # Static assets (if needed)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run a self-test to verify nothing is broken:
   ```python
   python -c "from chaos_tester import ChaosConfig, ChaosTestRunner; print('OK')"
   ```
5. Commit your changes (`git commit -m 'Add my feature'`)
6. Push to the branch (`git push origin feature/my-feature`)
7. Open a Pull Request

### Adding a New Test Module

1. Create a new file in `modules/` that subclasses `BaseModule`
2. Set `MODULE_NAME` to a short identifier
3. Implement the `run(self, discovered_pages)` method
4. Register it in `modules/__init__.py`
5. Add a toggle in `config.py` and wire it into `runner.py`

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
