"""
Performance metrics module - calls Google PageSpeed Insights API
for both mobile and desktop strategies and returns structured
Lighthouse metrics (FCP, SI, LCP, CLS, TTI, TBT).

Supports optional API key via GOOGLE_PSI_API_KEY env var for
higher rate limits. Includes retry with exponential backoff
for 429 (rate-limit) responses.
"""
import logging
import os
import time
import requests

logger = logging.getLogger(__name__)
PSI_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
API_KEY = os.environ.get("GOOGLE_PSI_API_KEY", "")

METRICS_MAP = {
    "first-contentful-paint":    ("First Contentful Paint",    "s"),
    "speed-index":               ("Speed Index",               "s"),
    "largest-contentful-paint":  ("Largest Contentful Paint",   "s"),
    "cumulative-layout-shift":   ("Cumulative Layout Shift",    ""),
    "interactive":               ("Time to Interactive",        "s"),
    "total-blocking-time":       ("Total Blocking Time",        "ms"),
}

MAX_RETRIES = 3
BACKOFF_BASE = 5


def _fetch_strategy(url, strategy, timeout=60):
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if API_KEY:
        params["key"] = API_KEY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("PSI %s attempt %d/%d for %s", strategy, attempt, MAX_RETRIES, url)
            resp = requests.get(PSI_API, params=params, timeout=timeout)

            if resp.status_code == 429:
                wait = BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "PSI %s rate-limited (429) for %s - retrying in %ds (attempt %d/%d)",
                    strategy, url, wait, attempt, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    continue
                else:
                    logger.error("PSI %s exhausted retries (429) for %s", strategy, url)
                    return {}

            resp.raise_for_status()
            data = resp.json()
            break

        except requests.exceptions.HTTPError as exc:
            logger.warning("PSI %s HTTP error for %s: %s", strategy, url, exc)
            return {}
        except requests.exceptions.Timeout:
            logger.warning("PSI %s timed out for %s (attempt %d)", strategy, url, attempt)
            if attempt < MAX_RETRIES:
                continue
            return {}
        except Exception as exc:
            logger.warning("PSI %s fetch failed for %s: %s", strategy, url, exc)
            return {}
    else:
        return {}

    audits = data.get("lighthouseResult", {}).get("audits", {})
    categories = data.get("lighthouseResult", {}).get("categories", {})
    perf_score = categories.get("performance", {}).get("score")

    if perf_score is None:
        logger.warning("PSI %s returned no performance score for %s", strategy, url)

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

    logger.info("PSI %s done for %s - score=%.2f, %d metrics",
                strategy, url, perf_score or 0, len(metrics))
    return {"score": perf_score, "metrics": metrics}


def fetch_performance_metrics(url, timeout=90):
    """Fetch Lighthouse metrics for both mobile and desktop."""
    logger.info("Fetching PageSpeed Insights for %s (key=%s)",
                url, "set" if API_KEY else "not set")
    result = {}
    for strategy in ("mobile", "desktop"):
        result[strategy] = _fetch_strategy(url, strategy, timeout=timeout)
    return result
