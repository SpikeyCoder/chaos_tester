"""
Performance metrics module - calls Google PageSpeed Insights API
for both mobile and desktop strategies and returns structured
Lighthouse metrics (FCP, SI, LCP, CLS, TTI, TBT).

Supports optional API key via GOOGLE_PSI_API_KEY env var for
higher rate limits. Includes smart retry logic with staggered
starts, immediate retry on 500, and tiered timeouts.
"""
import logging
import os
import re
import time
import threading
import requests

logger = logging.getLogger(__name__)
PSI_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
API_KEY = os.environ.get("GOOGLE_PSI_API_KEY", "")

# In-memory cache: url -> {timestamp, data}
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 900  # 15 minutes

METRICS_MAP = {
    "first-contentful-paint":    ("First Contentful Paint",    "s"),
    "speed-index":               ("Speed Index",               "s"),
    "largest-contentful-paint":  ("Largest Contentful Paint",   "s"),
    "cumulative-layout-shift":   ("Cumulative Layout Shift",    ""),
    "interactive":               ("Time to Interactive",        "s"),
    "total-blocking-time":       ("Total Blocking Time",        "ms"),
}

MAX_RETRIES = 3
FIRST_ATTEMPT_TIMEOUT = 45
RETRY_TIMEOUT = 45


def _fetch_strategy(url, strategy):
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if API_KEY:
        params["key"] = API_KEY

    strategy_start = time.time()
    for attempt in range(1, MAX_RETRIES + 1):
        # First attempt gets shorter timeout, retry gets longer
        timeout = FIRST_ATTEMPT_TIMEOUT if attempt == 1 else RETRY_TIMEOUT

        try:
            attempt_start = time.time()
            logger.info("PSI %s attempt %d/%d for %s (timeout=%ds, strategy_elapsed=%.1fs)",
                        strategy, attempt, MAX_RETRIES, url, timeout,
                        time.time() - strategy_start)
            resp = requests.get(PSI_API, params=params, timeout=timeout)
            logger.info("PSI %s response %d in %.1fs (attempt %d, strategy_total=%.1fs)",
                        strategy, resp.status_code, time.time() - attempt_start,
                        attempt, time.time() - strategy_start)

            if resp.status_code == 429:
                # Rate limited: sleep before retry (only case where we sleep)
                wait = 5 * (2 ** (attempt - 1))
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

            if resp.status_code >= 500:
                # Server error: retry immediately (no sleep)
                logger.warning(
                    "PSI %s server error (%d) for %s - retrying immediately (attempt %d/%d)",
                    strategy, resp.status_code, url, attempt, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    continue
                else:
                    logger.error("PSI %s exhausted retries (500) for %s", strategy, url)
                    return {}

            resp.raise_for_status()
            data = resp.json()
            break

        except requests.exceptions.Timeout:
            logger.warning("PSI %s timed out after %ds for %s (attempt %d, strategy_total=%.1fs)",
                           strategy, timeout, url, attempt, time.time() - strategy_start)
            # Retry immediately (no sleep) on timeout
            if attempt < MAX_RETRIES:
                continue
            return {}
        except requests.exceptions.HTTPError as exc:
            logger.warning("PSI %s HTTP error for %s: %s", strategy, url, exc)
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

    # Extract Lighthouse opportunities (performance recommendations)
    recommendations = []
    for audit_id, audit_data in audits.items():
        details_obj = audit_data.get("details", {})
        overall_savings_ms = details_obj.get("overallSavingsMs", 0)
        overall_savings_bytes = details_obj.get("overallSavingsBytes", 0)
        audit_score = audit_data.get("score")

        # Include if: has savings potential OR score is below 0.9 (not passing)
        has_savings = overall_savings_ms > 0 or overall_savings_bytes > 50000
        is_failing = audit_score is not None and audit_score < 0.9
        # Skip informational/not-applicable audits
        if audit_data.get("scoreDisplayMode") in ("notApplicable", "manual", "informative"):
            continue
        if has_savings or (is_failing and audit_data.get("title")):
            display = audit_data.get("displayValue", "")
            title = audit_data.get("title", audit_id.replace("-", " ").title())
            description = audit_data.get("description", "")
            # Clean markdown links from description
            description = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", description)
            recommendations.append({
                "id": audit_id,
                "title": title,
                "description": description[:200],
                "display": display,
                "savings_ms": overall_savings_ms,
                "savings_bytes": overall_savings_bytes,
                "score": audit_score if audit_score is not None else 1,
            })
    # Sort: worst scores first, then by potential savings
    recommendations.sort(key=lambda x: (x["score"], -x["savings_ms"], -x["savings_bytes"]))

    # Fallback: if no Lighthouse opportunities, generate recommendations from metric scores
    if not recommendations:
        for audit_id, (label, unit) in METRICS_MAP.items():
            audit = audits.get(audit_id, {})
            m_score = audit.get("score")
            if m_score is not None and m_score < 0.9:
                tips = {
                    "first-contentful-paint": "Reduce server response time, eliminate render-blocking resources, and optimize CSS delivery.",
                    "speed-index": "Minimize main-thread work, reduce JavaScript execution time, and ensure content is visible during load.",
                    "largest-contentful-paint": "Optimize images (use WebP/AVIF), preload critical resources, and use a CDN for faster delivery.",
                    "cumulative-layout-shift": "Set explicit dimensions on images/videos, avoid inserting content above existing content, and use CSS containment.",
                    "interactive": "Reduce JavaScript payload, defer non-critical scripts, and minimize main-thread blocking time.",
                    "total-blocking-time": "Break up long tasks, defer unused JavaScript, and minimize third-party script impact.",
                }
                recommendations.append({
                    "id": audit_id,
                    "title": f"Improve {label}",
                    "description": tips.get(audit_id, f"Optimize {label} to improve overall performance."),
                    "display": audit.get("displayValue", ""),
                    "savings_ms": 0,
                    "savings_bytes": 0,
                    "score": m_score,
                })

    logger.info("PSI %s done for %s - score=%.2f, %d metrics, %d recommendations",
                strategy, url, perf_score or 0, len(metrics), len(recommendations))
    return {"score": perf_score, "metrics": metrics, "recommendations": recommendations[:5]}


def _get_cached(url):
    """Return cached PSI result if fresh, else None."""
    with _cache_lock:
        entry = _cache.get(url)
        if entry and (time.time() - entry["timestamp"]) < CACHE_TTL_SECONDS:
            logger.info("PSI cache hit for %s (age=%.0fs)", url, time.time() - entry["timestamp"])
            return entry["data"]
    return None


def _set_cache(url, data):
    """Store PSI result in cache."""
    with _cache_lock:
        _cache[url] = {"timestamp": time.time(), "data": data}
        # Evict stale entries (keep cache small)
        stale_keys = [k for k, v in _cache.items() if (time.time() - v["timestamp"]) > CACHE_TTL_SECONDS * 2]
        for k in stale_keys:
            del _cache[k]


def fetch_performance_metrics(url):
    """Fetch Lighthouse metrics for both mobile and desktop SEQUENTIALLY.
    Sequential execution avoids connection contention on Cloud Run instances
    that are simultaneously running other audit modules. Each strategy gets
    the full timeout budget without competing for resources.
    Returns cached results if the same URL was fetched within the last 15 minutes."""
    # Check cache first
    cached = _get_cached(url)
    if cached is not None:
        return cached

    logger.info("Fetching PageSpeed Insights for %s (key=%s, sequential)",
                url, "set" if API_KEY else "not set")

    result = {}

    # Run desktop first, then mobile -- sequential to avoid timeout contention
    for strategy in ("desktop", "mobile"):
        try:
            result[strategy] = _fetch_strategy(url, strategy)
        except Exception as exc:
            logger.warning("PSI %s failed: %s", strategy, exc)
            result[strategy] = {}
        # Brief pause between strategies to be polite to the API
        if strategy == "desktop":
            time.sleep(2)

    if not any(result.get(s, {}).get("score") is not None for s in result):
        logger.warning("PSI returned no usable data for %s -- both strategies empty", url)
    else:
        _set_cache(url, result)
    return result
