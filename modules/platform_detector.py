"""
Module -- Platform Detector

Detects the web platform/hosting from HTTP response headers and HTML content.
Runs after the availability module to leverage existing crawl data.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("chaos_tester")


# Platform detection rules: each entry has a name, display name,
# fix file name, and detection functions for headers and HTML.
PLATFORM_RULES = [
    {
        "name": "wordpress",
        "display": "WordPress",
        "fix_file": "functions.php",
        "header_checks": [
            lambda h: "php" in h.get("x-powered-by", "").lower(),
        ],
        "html_checks": [
            lambda html: bool(re.search(r'<meta[^>]*generator[^>]*wordpress', html, re.I)),
            lambda html: "wp-content" in html,
        ],
    },
    {
        "name": "shopify",
        "display": "Shopify",
        "fix_file": "theme.liquid",
        "header_checks": [
            lambda h: "x-shopify-stage" in h,
            lambda h: "shopify" in h.get("x-powered-by", "").lower(),
            lambda h: "shopify" in h.get("server", "").lower(),
        ],
        "html_checks": [
            lambda html: "cdn.shopify.com" in html,
        ],
    },
    {
        "name": "cloudflare_pages",
        "display": "Cloudflare Pages",
        "fix_file": "_headers",
        "header_checks": [
            lambda h: "cf-ray" in h and "cloudflare" in h.get("server", "").lower(),
        ],
        "html_checks": [],
    },
    {
        "name": "netlify",
        "display": "Netlify",
        "fix_file": "netlify.toml",
        "header_checks": [
            lambda h: "x-nf-request-id" in h,
            lambda h: "netlify" in h.get("server", "").lower(),
        ],
        "html_checks": [],
    },
    {
        "name": "vercel",
        "display": "Vercel",
        "fix_file": "vercel.json",
        "header_checks": [
            lambda h: "x-vercel-id" in h,
            lambda h: "vercel" in h.get("server", "").lower(),
        ],
        "html_checks": [],
    },
    {
        "name": "nginx",
        "display": "Nginx",
        "fix_file": "nginx.conf",
        "header_checks": [
            lambda h: "nginx" in h.get("server", "").lower(),
        ],
        "html_checks": [],
    },
    {
        "name": "apache",
        "display": "Apache",
        "fix_file": ".htaccess",
        "header_checks": [
            lambda h: "apache" in h.get("server", "").lower(),
        ],
        "html_checks": [],
    },
]

UNKNOWN_PLATFORM = {
    "name": "unknown",
    "display": "Generic Web Server",
    "fix_file": "server-config",
}


def detect_platform(response_headers: dict, html_content: str = "") -> dict:
    """Detect the website platform from response headers and HTML.

    Args:
        response_headers: HTTP response headers (case-insensitive dict).
        html_content: HTML body of the page (optional, used for CMS detection).

    Returns:
        dict with keys: name, display, fix_file
    """
    # Normalize headers to lowercase keys for consistent matching
    lower_headers = {k.lower(): v for k, v in response_headers.items()}

    for rule in PLATFORM_RULES:
        # Check header-based rules
        for check in rule["header_checks"]:
            try:
                if check(lower_headers):
                    logger.info("Platform detected: %s (via headers)", rule["display"])
                    return {
                        "name": rule["name"],
                        "display": rule["display"],
                        "fix_file": rule["fix_file"],
                    }
            except Exception:
                continue

        # Check HTML-based rules
        if html_content:
            for check in rule.get("html_checks", []):
                try:
                    if check(html_content):
                        logger.info("Platform detected: %s (via HTML)", rule["display"])
                        return {
                            "name": rule["name"],
                            "display": rule["display"],
                            "fix_file": rule["fix_file"],
                        }
                except Exception:
                    continue

    logger.info("Platform detection: no specific platform identified, using generic")
    return dict(UNKNOWN_PLATFORM)


def detect_platform_from_crawl(page_cache: dict) -> dict:
    """Detect platform from existing crawl data (page_cache from availability module).

    Args:
        page_cache: dict mapping URL -> (response, error, duration_ms)

    Returns:
        dict with keys: name, display, fix_file
    """
    for url, (resp, err, dt) in page_cache.items():
        if resp is None:
            continue
        headers = dict(resp.headers)
        try:
            html = resp.text[:50000] if hasattr(resp, "text") else ""
        except Exception:
            html = ""
        result = detect_platform(headers, html)
        if result["name"] != "unknown":
            return result

    # If no specific platform found from any page, try the first response
    for url, (resp, err, dt) in page_cache.items():
        if resp is not None:
            return detect_platform(dict(resp.headers), "")

    return dict(UNKNOWN_PLATFORM)
