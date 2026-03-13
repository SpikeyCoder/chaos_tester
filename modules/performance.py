"""
Performance metrics module - calls Google PageSpeed Insights API
for both mobile and desktop strategies and returns structured
Lighthouse metrics (FCP, SI, LCP, CLS, TTI, TBT).
"""
import logging
import requests

logger = logging.getLogger(__name__)
PSI_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

METRICS_MAP = {
    "first-contentful-paint":    ("First Contentful Paint",    "s"),
    "speed-index":               ("Speed Index",               "s"),
    "largest-contentful-paint":  ("Largest Contentful Paint",   "s"),
    "cumulative-layout-shift":   ("Cumulative Layout Shift",    ""),
    "interactive":               ("Time to Interactive",        "s"),
    "total-blocking-time":       ("Total Blocking Time",        "ms"),
}


def _fetch_strategy(url, strategy, timeout=60):
    try:
        resp = requests.get(
            PSI_API,
            params={"url": url, "strategy": strategy, "category": "performance"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("PSI %s fetch failed for %s: %s", strategy, url, exc)
        return {}

    audits = data.get("lighthouseResult", {}).get("audits", {})
    categories = data.get("lighthouseResult", {}).get("categories", {})
    perf_score = categories.get("performance", {}).get("score")

    metrics = {}
    for audit_id, (label, unit) in METRICS_MAP.items():
        audit = audits.get(audit_id, {})
        raw = audit.get("numericValue")
        score = audit.get("score")
        display = audit.get("displayValue", "")
        if raw is not None:
            if unit == "s" and raw > 10:
                value = round(raw / 1000, 1)
            elif unit == "":
                value = round(raw, 3)
            else:
                value = round(raw, 0)
            metrics[audit_id] = {
                "label": label,
                "value": value,
                "unit": unit,
                "score": score,
                "display": display,
            }

    return {"score": perf_score, "metrics": metrics}


def fetch_performance_metrics(url, timeout=90):
    logger.info("Fetching PageSpeed Insights for %s", url)
    result = {}
    for strategy in ("mobile", "desktop"):
        result[strategy] = _fetch_strategy(url, strategy, timeout=timeout)
    return result