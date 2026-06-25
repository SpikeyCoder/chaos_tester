"""
Module -- Fix Generator

Post-processing step that generates platform-specific fix snippets for
each finding that has a recommendation. Runs after all audit modules
complete and after platform detection.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("chaos_tester")

# ---------- Impact scoring benchmarks ($/page/year) ----------

IMPACT_BENCHMARKS = {
    "security": 300,
    "auth": 200,
    "accessibility": 200,
    "chaos": 100,
    "links": 50,
    "forms": 50,
    "availability": 50,
}

SEVERITY_MULTIPLIER = {
    "critical": 2.0,
    "high": 1.5,
    "medium": 1.0,
    "low": 0.5,
    "info": 0.1,
}

# ---------- Build-time-to-fix estimation (developer minutes) ----------
#
# Concrete, tunable companion to compute_impact(). It deliberately reuses the
# SAME finding inputs as compute_impact (module, severity, status) instead of
# introducing a parallel scoring model, so the two stay in lock-step.
#
# BUILD_TIME_BASE_MINUTES = typical hands-on developer minutes to implement the
# DOMINANT fix type for each module, assuming the engineer has the fix snippet
# in hand (which the report provides). Assumptions, per module:
#   security     : add/adjust HTTP security headers via platform config —
#                  well-trodden copy-paste, but needs a deploy + re-scan.
#   auth         : session/login/cookie config changes — must be done carefully
#                  and the full auth flow re-tested, so noticeably longer.
#   accessibility: per-element markup edits (alt text, form labels) — simple but
#                  repetitive; real effort scales with how many elements.
#   chaos        : performance / resilience work — profiling plus code changes,
#                  the most open-ended category.
#   forms        : markup + validation fixes on a form — moderate.
#   links        : update or redirect broken URLs — quick edits.
#   availability : chase down 5xx / timeout pages — variable, infra-adjacent.
#
# Tune these two tables to recalibrate; nothing else needs to change.
BUILD_TIME_BASE_MINUTES = {
    "security": 20,
    "auth": 60,
    "accessibility": 25,
    "chaos": 120,
    "forms": 30,
    "links": 15,
    "availability": 90,
}

# Severity scales the base effort: a critical instance usually means more
# occurrences and more careful implementation + verification than a low one.
BUILD_TIME_SEVERITY_MULTIPLIER = {
    "critical": 2.0,
    "high": 1.5,
    "medium": 1.0,
    "low": 0.6,
    "info": 0.4,
}

# Fallback hands-on minutes for an unrecognised module.
BUILD_TIME_DEFAULT_MINUTES = 30

# ---------- Fix templates per platform ----------

def _csp_fix(platform_name):
    """Return CSP header fix snippet for a given platform."""
    fixes = {
        "cloudflare_pages": {
            "fix_filename": "_headers",
            "fix_snippet": (
                "/*\n"
                "  Content-Security-Policy: default-src 'self'; "
                "script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "font-src 'self'; connect-src 'self'; frame-ancestors 'none'\n"
            ),
            "fix_instructions": (
                "1. Create a _headers file in your project root\n"
                "2. Paste the snippet above\n"
                "3. Deploy via Cloudflare Pages (the file is auto-detected)"
            ),
        },
        "netlify": {
            "fix_filename": "netlify.toml",
            "fix_snippet": (
                "[[headers]]\n"
                '  for = "/*"\n'
                "  [headers.values]\n"
                '    Content-Security-Policy = "default-src \'self\'; '
                "script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "font-src 'self'; connect-src 'self'; frame-ancestors 'none'\"\n"
            ),
            "fix_instructions": (
                "1. Add the snippet to your netlify.toml file\n"
                "2. Deploy via Netlify (settings are applied automatically)"
            ),
        },
        "vercel": {
            "fix_filename": "vercel.json",
            "fix_snippet": (
                '{\n'
                '  "headers": [\n'
                '    {\n'
                '      "source": "/(.*)",\n'
                '      "headers": [\n'
                '        {\n'
                '          "key": "Content-Security-Policy",\n'
                '          "value": "default-src \'self\'; script-src \'self\'; '
                "style-src 'self'; img-src 'self' data:; font-src 'self'; "
                "connect-src 'self'; frame-ancestors 'none'\"\n"
                '        }\n'
                '      ]\n'
                '    }\n'
                '  ]\n'
                '}\n'
            ),
            "fix_instructions": (
                "1. Add or update vercel.json in your project root\n"
                "2. Deploy via Vercel CLI or git push"
            ),
        },
        "apache": {
            "fix_filename": ".htaccess",
            "fix_snippet": (
                "Header always set Content-Security-Policy "
                "\"default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                "frame-ancestors 'none'\"\n"
            ),
            "fix_instructions": (
                "1. Add the snippet to your .htaccess file\n"
                "2. Make sure mod_headers is enabled: a2enmod headers"
            ),
        },
        "nginx": {
            "fix_filename": "nginx.conf",
            "fix_snippet": (
                "add_header Content-Security-Policy "
                "\"default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                "frame-ancestors 'none'\" always;\n"
            ),
            "fix_instructions": (
                "1. Add the snippet to your server{} or location{} block\n"
                "2. Reload nginx: sudo nginx -s reload"
            ),
        },
        "wordpress": {
            "fix_filename": "functions.php",
            "fix_snippet": (
                "// Add Content-Security-Policy header\n"
                "function wa_add_csp_header() {\n"
                "    header(\"Content-Security-Policy: default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                "frame-ancestors 'none'\");\n"
                "}\n"
                "add_action('send_headers', 'wa_add_csp_header');\n"
            ),
            "fix_instructions": (
                "1. Add this snippet to your theme's functions.php\n"
                "2. Note: WordPress often needs 'unsafe-inline' for scripts/styles"
            ),
        },
    }
    return fixes.get(platform_name, fixes.get("nginx", {}))


def _header_fix(header_name, header_value, platform_name):
    """Generate a fix for a missing HTTP header on a given platform."""
    templates = {
        "cloudflare_pages": {
            "fix_filename": "_headers",
            "fix_snippet": f"/*\n  {header_name}: {header_value}\n",
            "fix_instructions": f"Add to your _headers file in the project root.",
        },
        "netlify": {
            "fix_filename": "netlify.toml",
            "fix_snippet": (
                f'[[headers]]\n  for = "/*"\n  [headers.values]\n'
                f'    {header_name} = "{header_value}"\n'
            ),
            "fix_instructions": f"Add to your netlify.toml file.",
        },
        "vercel": {
            "fix_filename": "vercel.json",
            "fix_snippet": (
                f'{{\n  "headers": [{{\n    "source": "/(.*)",\n'
                f'    "headers": [{{"key": "{header_name}", '
                f'"value": "{header_value}"}}]\n  }}]\n}}\n'
            ),
            "fix_instructions": f"Add to vercel.json in your project root.",
        },
        "apache": {
            "fix_filename": ".htaccess",
            "fix_snippet": f'Header always set {header_name} "{header_value}"\n',
            "fix_instructions": "Add to your .htaccess file (requires mod_headers).",
        },
        "nginx": {
            "fix_filename": "nginx.conf",
            "fix_snippet": f'add_header {header_name} "{header_value}" always;\n',
            "fix_instructions": "Add to your server{} block, then reload nginx.",
        },
        "wordpress": {
            "fix_filename": "functions.php",
            "fix_snippet": (
                f'function wa_add_{header_name.lower().replace("-","_")}_header() {{\n'
                f'    header("{header_name}: {header_value}");\n'
                f'}}\n'
                f'add_action(\'send_headers\', \'wa_add_{header_name.lower().replace("-","_")}_header\');\n'
            ),
            "fix_instructions": "Add to your theme's functions.php file.",
        },
    }
    return templates.get(platform_name, templates.get("nginx", {}))


# ---------- Finding-to-fix mapping rules ----------

FIX_PATTERNS = [
    {
        "patterns": ["content-security-policy", "csp"],
        "generator": lambda pn, **kw: _csp_fix(pn),
    },
    {
        "patterns": ["strict-transport-security", "hsts"],
        "generator": lambda pn, **kw: _header_fix(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
            pn,
        ),
    },
    {
        "patterns": ["x-frame-options", "clickjacking"],
        "generator": lambda pn, **kw: _header_fix(
            "X-Frame-Options", "DENY", pn,
        ),
    },
    {
        "patterns": ["x-content-type-options", "mime sniffing"],
        "generator": lambda pn, **kw: _header_fix(
            "X-Content-Type-Options", "nosniff", pn,
        ),
    },
    {
        "patterns": ["referrer-policy"],
        "generator": lambda pn, **kw: _header_fix(
            "Referrer-Policy", "strict-origin-when-cross-origin", pn,
        ),
    },
    {
        "patterns": ["permissions-policy"],
        "generator": lambda pn, **kw: _header_fix(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
            pn,
        ),
    },
    {
        "patterns": ["meta description", "missing description"],
        "generator": lambda pn, **kw: {
            "fix_filename": "index.html",
            "fix_snippet": '<meta name="description" content="Your page description here (140-160 characters)">',
            "fix_instructions": (
                "Add this tag inside the <head> section of your HTML.\n"
                "Write a unique, compelling description for each page."
            ),
        },
    },
    {
        "patterns": ["alt text", "missing alt", "alt attribute"],
        "generator": lambda pn, **kw: {
            "fix_filename": "index.html",
            "fix_snippet": '<img src="image.jpg" alt="Descriptive text about the image">',
            "fix_instructions": (
                "Add a descriptive alt attribute to every <img> tag.\n"
                "Describe what the image shows for screen reader users."
            ),
        },
    },
    {
        "patterns": ["open graph", "og:"],
        "generator": lambda pn, **kw: {
            "fix_filename": "index.html",
            "fix_snippet": (
                '<meta property="og:title" content="Your Page Title">\n'
                '<meta property="og:description" content="Your page description">\n'
                '<meta property="og:image" content="https://yoursite.com/image.jpg">\n'
                '<meta property="og:url" content="https://yoursite.com/">\n'
                '<meta property="og:type" content="website">'
            ),
            "fix_instructions": "Add these Open Graph meta tags inside the <head> section.",
        },
    },
    {
        "patterns": ["robots.txt", "sitemap"],
        "generator": lambda pn, **kw: {
            "fix_filename": "robots.txt",
            "fix_snippet": (
                "User-agent: *\n"
                "Allow: /\n\n"
                "Sitemap: https://yoursite.com/sitemap.xml\n"
            ),
            "fix_instructions": "Place this file at the root of your website.",
        },
    },
    {
        "patterns": ["structured data", "schema.org", "json-ld"],
        "generator": lambda pn, **kw: {
            "fix_filename": "index.html",
            "fix_snippet": (
                '<script type="application/ld+json">\n'
                '{\n'
                '  "@context": "https://schema.org",\n'
                '  "@type": "LocalBusiness",\n'
                '  "name": "Your Business Name",\n'
                '  "address": {\n'
                '    "@type": "PostalAddress",\n'
                '    "streetAddress": "123 Main St",\n'
                '    "addressLocality": "City",\n'
                '    "addressRegion": "State",\n'
                '    "postalCode": "12345"\n'
                '  },\n'
                '  "telephone": "+1-555-555-5555",\n'
                '  "url": "https://yoursite.com"\n'
                '}\n'
                '</script>'
            ),
            "fix_instructions": "Add this JSON-LD block before the closing </head> tag.",
        },
    },
    {
        "patterns": ["form label", "missing label", "input.*label"],
        "generator": lambda pn, **kw: {
            "fix_filename": "index.html",
            "fix_snippet": (
                '<label for="email">Email Address</label>\n'
                '<input type="email" id="email" name="email">'
            ),
            "fix_instructions": (
                "Wrap each form input with a <label> element, or use the\n"
                "'for' attribute to associate the label with the input's 'id'."
            ),
        },
    },
]


def _match_fix(finding_text: str, platform_name: str) -> Optional[dict]:
    """Match a finding to a fix template based on pattern matching."""
    text = finding_text.lower()
    for rule in FIX_PATTERNS:
        for pattern in rule["patterns"]:
            if re.search(pattern, text, re.I):
                try:
                    return rule["generator"](platform_name)
                except Exception as exc:
                    logger.warning("Fix generation failed for pattern %s: %s", pattern, exc)
                    return None
    return None


def generate_fix_for_result(result: dict, platform: dict) -> dict:
    """Generate a platform-specific fix for a single result dict.

    Mutates the result dict in place by adding fix_snippet, fix_filename,
    fix_instructions, impact_estimate, and impact_pages fields.

    Returns the result dict for chaining.
    """
    platform_name = platform.get("name", "unknown")

    # Build search text from all relevant fields
    search_text = " ".join([
        result.get("name", ""),
        result.get("description", ""),
        result.get("recommendation", ""),
        result.get("details", ""),
    ])

    fix = _match_fix(search_text, platform_name)
    if fix:
        result["fix_snippet"] = fix.get("fix_snippet", "")
        result["fix_filename"] = fix.get("fix_filename", platform.get("fix_file", "config"))
        result["fix_instructions"] = fix.get("fix_instructions", "")
        result["has_fix"] = True
    else:
        result["has_fix"] = False

    return result


def compute_impact(result: dict, total_pages: int) -> dict:
    """Compute business impact scoring for a single result dict.

    Mutates the result dict in place by adding impact_pages and
    impact_estimate fields.

    Returns the result dict for chaining.
    """
    module = result.get("module", "")
    severity = result.get("severity", "info")
    status = result.get("status", "passed")

    # Only compute impact for non-passing results
    if status in ("passed", "skipped"):
        result["impact_pages"] = 0
        result["impact_estimate"] = 0
        return result

    # Determine pages affected: security/header issues affect all pages,
    # page-specific issues affect 1 page
    if module in ("security", "auth"):
        pages_affected = total_pages
    elif result.get("url"):
        pages_affected = 1
    else:
        pages_affected = max(1, total_pages // 2)

    base_rate = IMPACT_BENCHMARKS.get(module, 50)
    multiplier = SEVERITY_MULTIPLIER.get(severity, 0.5)
    estimate = int(pages_affected * base_rate * multiplier)

    result["impact_pages"] = pages_affected
    result["impact_estimate"] = estimate

    return result


def _humanize_minutes(minutes: int) -> str:
    """Render a minutes estimate as a tidy, human-friendly label.

    < 1 hour  -> "~N min"  (rounded to the nearest 5 minutes)
    < 8 hours -> "~N hr(s)" (rounded to the nearest half hour)
    >= 8 hrs  -> "~N day(s)" (rounded to the nearest half, 8-hour day)
    """
    if minutes <= 0:
        return ""
    if minutes < 60:
        rounded = max(5, int(round(minutes / 5.0)) * 5)
        return f"~{rounded} min"
    hours = minutes / 60.0
    if hours < 8:
        half = round(hours * 2) / 2
        if half == int(half):
            n = int(half)
            return f"~{n} hr" if n == 1 else f"~{n} hrs"
        return f"~{half} hrs"
    days = hours / 8.0  # assume an 8-hour engineering day
    half = round(days * 2) / 2
    if half == int(half):
        n = int(half)
        return f"~{n} day" if n == 1 else f"~{n} days"
    return f"~{half} days"


def estimate_build_time(result: dict) -> dict:
    """Estimate developer time-to-implement for a single finding's fix.

    Concrete, per-finding companion to compute_impact(). Reuses the same
    inputs (module, severity, status) rather than introducing a new model.
    Mutates the result dict in place, adding:
      build_time_minutes : int  estimated hands-on minutes (0 for passing)
      build_time_label   : str  human label, e.g. "~30 min" / "~2 hrs"

    Returns the result dict for chaining.
    """
    module = result.get("module", "")
    severity = result.get("severity", "info")
    status = result.get("status", "passed")

    # No work to do for passing/skipped checks — mirrors compute_impact().
    if status in ("passed", "skipped"):
        result["build_time_minutes"] = 0
        result["build_time_label"] = ""
        return result

    base = BUILD_TIME_BASE_MINUTES.get(module, BUILD_TIME_DEFAULT_MINUTES)
    multiplier = BUILD_TIME_SEVERITY_MULTIPLIER.get(severity, 1.0)
    minutes = max(5, int(round(base * multiplier)))

    result["build_time_minutes"] = minutes
    result["build_time_label"] = _humanize_minutes(minutes)

    return result


def generate_fixes_for_report(report_data: dict, platform: dict) -> dict:
    """Post-process a full report: add fixes and impact to every result.

    Mutates report_data in place. Adds platform info and
    total_annual_impact to the report.

    Returns the report_data dict.
    """
    results = report_data.get("results", [])
    total_pages = len(set(
        r.get("url", "") for r in results
        if r.get("module") == "availability"
        and "Page load" in r.get("name", "")
        and r.get("status") == "passed"
    )) or 1

    report_data["platform"] = platform
    total_impact = 0

    for result in results:
        generate_fix_for_result(result, platform)
        compute_impact(result, total_pages)
        estimate_build_time(result)
        total_impact += result.get("impact_estimate", 0)

    report_data["total_annual_impact"] = total_impact
    report_data["total_pages_audited"] = total_pages

    fix_count = sum(1 for r in results if r.get("has_fix"))
    logger.info(
        "Fix generation complete: %d fixes generated, $%d total annual impact, "
        "%d pages audited, platform=%s",
        fix_count, total_impact, total_pages, platform.get("display", "unknown"),
    )

    return report_data
