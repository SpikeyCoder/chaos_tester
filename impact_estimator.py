"""
Chaos Tester / Website Auditor -- Business-impact & fix-effort estimation.

Every finding shown in a report gets two human-facing estimates, derived ONLY
from data we already collect for each test (its `severity` and its `module`):

  1. estimate_dollar_impact()  -> an annual dollar figure (USD/year)
  2. estimate_fix_time()       -> a developer build-time estimate to fix it

Both are deliberately TRANSPARENT, DOCUMENTED HEURISTICS, not precise numbers.
They exist so a non-technical site owner can triage "what is this costing me
and how much work is it to fix". Tune the lookup tables below to taste -- every
number lives in one place and is annotated with its reasoning.

----------------------------------------------------------------------------
DOLLAR-IMPACT MODEL  (interpretation: ANNUAL REVENUE / COST AT RISK)
----------------------------------------------------------------------------
We model the *annual* revenue or cost a typical small-business site is exposed
to while the issue is left unfixed -- NOT a one-time remediation cost. This is
the most defensible reading for an SMB audit tool and matches the "$X/yr"
framing in the product design. The figure is:

    dollar_impact = SEVERITY_BASELINE_USD[severity] * MODULE_WEIGHT[module]

  * SEVERITY_BASELINE_USD -- how much annual exposure a finding of this
    severity represents, before accounting for what kind of issue it is.
  * MODULE_WEIGHT -- how directly this *category* of issue maps to lost money.
    Forms (lost leads/sales) and security (breach + SEO penalty) hit revenue
    harder than, say, a broken link, so they carry a higher weight.

----------------------------------------------------------------------------
FIX build-TIME MODEL  (interpretation: DEVELOPER TIME TO IMPLEMENT THE FIX)
----------------------------------------------------------------------------
    minutes = SEVERITY_FIX_MINUTES[severity] * MODULE_FIX_FACTOR[module]

  * SEVERITY_FIX_MINUTES -- rough build time by severity. Higher-severity
    issues tend to need more careful work + testing.
  * MODULE_FIX_FACTOR -- some categories are inherently more involved to fix
    regardless of severity (security/header/TLS config, auth/session logic)
    while others are usually a one-liner (a single broken link).

The minute total is then rendered to a friendly label ("~30 minutes",
"~2 hours", "~1 day"). This REPLACES the old habit of showing a test's raw
execution time (`duration_ms`, e.g. "0ms") as if it were a fix estimate.

All inputs are lower-cased and unknown severities/modules fall back to safe
neutral defaults, so this never raises for an unexpected value.
"""

from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# Dollar-impact tables  (tune these)
# ---------------------------------------------------------------------------

# Annual revenue/cost at risk, in USD, for a finding of each severity,
# before the per-category weight is applied. "info" is treated as $0 because
# informational findings are not a live risk.
SEVERITY_BASELINE_USD: Dict[str, int] = {
    "critical": 9000,
    "high":     4000,
    "medium":   1500,
    "low":      400,
    "info":     0,
}

# Per-module multiplier on the baseline. 1.0 = neutral. Raise it for categories
# that map directly to lost revenue, lower it for softer/indirect impact.
MODULE_WEIGHT: Dict[str, float] = {
    "forms":        1.5,   # broken/insecure forms = direct lost leads & sales
    "security":     1.3,   # breach/defacement/data-leak risk + Google SEO penalty
    "availability": 1.2,   # unreachable pages = lost traffic + de-indexing
    "auth":         1.1,   # lockouts -> support cost + account churn
    "chaos":        1.0,   # performance/stress -> slower conversion (baseline)
    "links":        0.6,   # broken links = softer UX/SEO impact
}

# Neutral default weight for any module not listed above.
DEFAULT_MODULE_WEIGHT = 1.0

# ---------------------------------------------------------------------------
# Fix build-time tables  (tune these)
# ---------------------------------------------------------------------------

# Baseline developer minutes to implement a fix, by severity.
SEVERITY_FIX_MINUTES: Dict[str, int] = {
    "info":     5,
    "low":      15,
    "medium":   30,
    "high":     120,
    "critical": 240,
}

# Per-module factor on the baseline minutes. >1 = more involved category,
# <1 = usually a quick/localised change.
MODULE_FIX_FACTOR: Dict[str, float] = {
    "security":     1.5,   # header/CSP/TLS config + re-testing
    "auth":         1.5,   # session/login logic is fiddly to change safely
    "chaos":        1.25,  # performance work (images, bundles, caching)
    "availability": 1.0,
    "forms":        1.0,
    "links":        0.5,   # often a single URL change
}

DEFAULT_FIX_FACTOR = 1.0
DEFAULT_FIX_MINUTES = 120  # used only if severity is completely unrecognised


def estimate_dollar_impact(severity: str, module: str) -> int:
    """Estimated ANNUAL revenue/cost at risk for a finding, in whole USD.

    Returns 0 for informational findings (no live risk). Never raises.
    """
    sev = (severity or "").lower()
    mod = (module or "").lower()
    baseline = SEVERITY_BASELINE_USD.get(sev, 0)
    weight = MODULE_WEIGHT.get(mod, DEFAULT_MODULE_WEIGHT)
    return int(round(baseline * weight))


def format_dollar_impact(amount: int) -> str:
    """Render a dollar figure for display, e.g. 6000 -> "$6,000/yr".

    A genuinely zero/unknowable impact renders as "Minimal" rather than a
    misleading "$0" or the old "$???" placeholder.
    """
    if not amount or amount <= 0:
        return "Minimal"
    return "${:,}/yr".format(int(amount))


def humanize_minutes(minutes: float) -> str:
    """Turn a minute count into a friendly build-time label."""
    m = max(1, int(round(minutes)))
    if m < 60:
        # round to the nearest 5 minutes for a tidy estimate
        m5 = max(5, int(round(m / 5.0)) * 5)
        return "~{} minutes".format(m5)
    if m < 8 * 60:
        hours = round(m / 60.0 * 2) / 2.0  # nearest half hour
        if hours == int(hours):
            hours = int(hours)
        return "~{} hour{}".format(hours, "" if hours == 1 else "s")
    days = round(m / (8 * 60.0) * 2) / 2.0  # 8-hour dev days, nearest half day
    if days == int(days):
        days = int(days)
    return "~{} day{}".format(days, "" if days == 1 else "s")


def estimate_fix_time(severity: str, module: str) -> Dict[str, object]:
    """Estimated developer build-time to implement the fix.

    Returns ``{"label": "~2 hours", "minutes": 120}``. ``minutes`` is exposed
    so callers can sort/aggregate; ``label`` is what the UI shows. Never raises.
    """
    sev = (severity or "").lower()
    mod = (module or "").lower()
    base = SEVERITY_FIX_MINUTES.get(sev, DEFAULT_FIX_MINUTES)
    factor = MODULE_FIX_FACTOR.get(mod, DEFAULT_FIX_FACTOR)
    minutes = int(round(base * factor))
    return {"label": humanize_minutes(minutes), "minutes": minutes}
