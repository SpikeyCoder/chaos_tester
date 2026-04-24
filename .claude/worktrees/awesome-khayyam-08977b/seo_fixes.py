#!/usr/bin/env python3
"""Apply all SEO audit fixes to website-auditor.io codebase."""
import os

# ============================================================
# FIX 1: Rewrite base.html with full SEO meta tags
# ============================================================
BASE_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Free Website Audit Tool - SEO, Security & Performance Scanner | Website Auditor{% endblock %}</title>
    <meta name="description" content="{% block meta_description %}Free website audit tool that checks SEO, broken links, security, forms, and performance in one click. No login required. Get a detailed report instantly.{% endblock %}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://website-auditor.io{{ request.path }}">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Website Auditor">
    <meta property="og:title" content="{% block og_title %}Free Website Audit Tool - One-Click SEO & Security Scanner{% endblock %}">
    <meta property="og:description" content="{% block og_description %}Audit any website for SEO issues, broken links, security vulnerabilities, and performance problems. Free, instant, no login required.{% endblock %}">
    <meta property="og:url" content="https://website-auditor.io{{ request.path }}">
    <meta property="og:image" content="https://website-auditor.io/static/og-image.png">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Free Website Audit Tool | Website Auditor">
    <meta name="twitter:description" content="One-click website audit for SEO, security, broken links & performance. Free and instant.">
    <meta name="twitter:image" content="https://website-auditor.io/static/og-image.png">

    <!-- JSON-LD Schema -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "Website Auditor",
        "url": "https://website-auditor.io",
        "description": "Free website audit tool that checks SEO, broken links, security, forms, and performance in one click.",
        "applicationCategory": "WebApplication",
        "operatingSystem": "Web",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD"
        },
        "creator": {
            "@type": "Organization",
            "name": "Website Auditor"
        }
    }
    </script>
    {% block extra_schema %}{% endblock %}

    <style>
/* -- Reset & Base ----------------------------------------- */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
    --bg:       #0f172a;
    --surface:  #1e293b;
    --border:   #334155;
    --text:     #e2e8f0;
    --text-muted: #94a3b8;
    --accent:   #38bdf8;
    --accent-hover: #7dd3fc;
    --success:  #4ade80;
    --warning:  #fbbf24;
    --danger:   #f87171;
    --mono:     'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}
html { font-size: 16px; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
                 Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}
a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent-hover); }

/* -- Layout ----------------------------------------------- */
.container { max-width: 1100px; margin: 0 auto; padding: 0 20px; }
.inner { display: flex; align-items: center; justify-content: space-between; }

/* -- Header ----------------------------------------------- */
header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 14px 0;
    position: sticky; top: 0; z-index: 50;
}
header h1 { font-size: 1.25rem; display: flex; align-items: center; gap: 8px; }
header h1 .robot { font-size: 1.4rem; }
nav { display: flex; gap: 18px; }
nav a { color: var(--text-muted); font-size: 0.9rem; transition: color .2s; }
nav a:hover, nav a.active { color: var(--accent); }

/* -- Cards ------------------------------------------------ */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px;
    margin-bottom: 24px;
}
.card h2 { font-size: 1.15rem; margin-bottom: 16px; }

/* -- Forms ------------------------------------------------ */
label { display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 4px; }
input[type="text"], input[type="number"], input[type="url"],
select, textarea {
    width: 100%;
    padding: 10px 14px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-size: 0.95rem;
    transition: border-color .2s;
}
input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--accent);
}
textarea { resize: vertical; min-height: 60px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }

/* -- Buttons ---------------------------------------------- */
.btn {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 10px 22px;
    border: none; border-radius: 6px;
    font-size: 0.95rem; font-weight: 600;
    cursor: pointer; transition: background .2s, transform .1s;
}
.btn:active { transform: scale(0.98); }
.btn-primary { background: var(--accent); color: var(--bg); }
.btn-primary:hover { background: var(--accent-hover); }
.btn-danger  { background: var(--danger); color: #fff; }

/* -- Checkboxes ------------------------------------------- */
.checkbox-grid { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }
.checkbox-grid label {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 0.9rem; color: var(--text); cursor: pointer;
}
.checkbox-grid input[type="checkbox"] { accent-color: var(--accent); width: 16px; height: 16px; }

/* -- Tables ----------------------------------------------- */
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th { text-align: left; padding: 10px 12px; background: var(--bg); color: var(--text-muted);
     font-weight: 600; border-bottom: 2px solid var(--border); }
td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
tr:hover td { background: rgba(56,189,248,0.04); }

/* -- Status badges ---------------------------------------- */
.badge {
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 0.8rem; font-weight: 600;
}
.badge-ok      { background: rgba(74,222,128,0.15); color: var(--success); }
.badge-warn    { background: rgba(251,191,36,0.15); color: var(--warning); }
.badge-fail    { background: rgba(248,113,113,0.15); color: var(--danger); }
.badge-running { background: rgba(56,189,248,0.15); color: var(--accent); }

/* -- Stats grid ------------------------------------------- */
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
.stat-card .value { font-size: 1.6rem; font-weight: 700; }
.stat-card .label { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }

/* -- Progress --------------------------------------------- */
.progress-bar { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
.progress-bar .fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width .4s; }

/* -- Utility ---------------------------------------------- */
.mt-1 { margin-top: 8px; }
.mt-2 { margin-top: 16px; }
.mt-3 { margin-top: 24px; }
.mb-2 { margin-bottom: 16px; }
.text-muted { color: var(--text-muted); }
.text-sm { font-size: 0.85rem; }
.mono { font-family: var(--mono); }
.hidden { display: none; }

/* -- SEO Content Section ---------------------------------- */
.seo-content {
    background: var(--surface);
    border-top: 1px solid var(--border);
    padding: 48px 0;
    margin-top: 48px;
}
.seo-content h2 { font-size: 1.5rem; margin-bottom: 16px; color: var(--accent); }
.seo-content h3 { font-size: 1.1rem; margin: 24px 0 8px; color: var(--text); }
.seo-content p { color: var(--text-muted); margin-bottom: 12px; max-width: 800px; }
.feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin: 24px 0; }
.feature-card { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
.feature-card h3 { margin-top: 0; font-size: 1rem; }
.feature-card p { font-size: 0.9rem; }

/* -- Footer ----------------------------------------------- */
footer {
    background: var(--surface);
    border-top: 1px solid var(--border);
    padding: 24px 0;
    margin-top: 48px;
    text-align: center;
}
footer p { color: var(--text-muted); font-size: 0.85rem; }
footer a { color: var(--accent); }
footer nav { justify-content: center; margin-top: 8px; }

/* -- Responsive ------------------------------------------- */
@media (max-width: 768px) {
    .form-row { grid-template-columns: 1fr; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .feature-grid { grid-template-columns: 1fr; }
}
</style>
{% block extra_head %}{% endblock %}
</head>
<body>
    <header>
        <div class="container inner">
            <h1><span class="robot" aria-hidden="true">&#x1F916;</span> Website Auditor</h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/latest">Latest Report</a>
                <a href="/features">Features</a>
                <a href="/how-it-works">How It Works</a>
            </nav>
        </div>
    </header>
    <main class="container" style="padding-top: 28px; padding-bottom: 48px;">
        {%- with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        {% for category, message in messages %}
        <div style="background:{% if category == 'warning' %}#7f1d1d{% else %}#1a3a2a{% endif %};padding:12px 16px;border-radius:8px;margin-bottom:16px;color:{% if category == 'warning' %}#fca5a5{% else %}#86efac{% endif %};font-size:0.9rem;">
            {{ message }}
        </div>
        {% endfor %}
        {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>

    {% block seo_content %}{% endblock %}

    <footer>
        <div class="container">
            <p>&copy; 2026 Website Auditor &mdash; Free website audit tool for SEO, security, and performance.</p>
            <nav>
                <a href="/features">Features</a>
                <a href="/how-it-works">How It Works</a>
                <a href="https://github.com/SpikeyCoder/chaos_tester" rel="noopener" target="_blank">GitHub</a>
            </nav>
        </div>
    </footer>
</body>
</html>'''

os.makedirs("templates", exist_ok=True)
with open("templates/base.html", "w") as f:
    f.write(BASE_HTML)
print("[OK] templates/base.html rewritten with SEO meta tags, schema, OG, footer")

# ============================================================
# FIX 2: Create features.html template
# ============================================================
FEATURES_HTML = r'''{% extends "base.html" %}
{% block title %}Features - Free Website Audit Tool | Website Auditor{% endblock %}
{% block meta_description %}Explore Website Auditor's features: broken link detection, SEO analysis, security scanning, form testing, performance monitoring, and more. All free, no login required.{% endblock %}
{% block og_title %}Features - Comprehensive Website Audit Tool{% endblock %}
{% block og_description %}Check broken links, SEO issues, security vulnerabilities, forms, and performance in one click.{% endblock %}

{% block extra_schema %}
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
        {
            "@type": "Question",
            "name": "What does Website Auditor check?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "Website Auditor checks page availability, broken links, forms and interactions, security headers, authentication flows, and overall site performance across your entire website."
            }
        },
        {
            "@type": "Question",
            "name": "Is Website Auditor free?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "Yes, Website Auditor is completely free with no page limits, no login required, and no feature restrictions."
            }
        },
        {
            "@type": "Question",
            "name": "How many pages can Website Auditor crawl?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "You can configure the crawler to check up to hundreds of pages per audit, with adjustable crawl depth, concurrency, and timeout settings."
            }
        }
    ]
}
</script>
{% endblock %}

{% block content %}
<h2 style="font-size:1.5rem; margin-bottom:24px;">&#x1F50D; Features</h2>

<div class="feature-grid">
    <div class="feature-card">
        <h3>&#x2705; Page Availability</h3>
        <p>Crawl your entire site and detect HTTP errors, redirects, timeouts, and unreachable pages. Know exactly which URLs are broken before your visitors do.</p>
    </div>
    <div class="feature-card">
        <h3>&#x1F517; Broken Link Detection</h3>
        <p>Find every broken internal and external link across your website. Identify 404 errors, redirect chains, and orphan pages that hurt SEO and user experience.</p>
    </div>
    <div class="feature-card">
        <h3>&#x1F4DD; Form & Interaction Testing</h3>
        <p>Validate that your forms, buttons, and interactive elements work correctly. Check for missing labels, required field validation, and accessibility compliance.</p>
    </div>
    <div class="feature-card">
        <h3>&#x1F512; Security Analysis</h3>
        <p>Audit security headers, HTTPS configuration, cookie security (SameSite, Secure, HttpOnly), mixed content warnings, and common vulnerability indicators.</p>
    </div>
    <div class="feature-card">
        <h3>&#x1F504; Chaos & Failure Injection</h3>
        <p>Test how your site handles failures with configurable chaos intensity. Simulate slow responses, errors, and edge cases to improve resilience.</p>
    </div>
    <div class="feature-card">
        <h3>&#x1F510; Auth & Session Testing</h3>
        <p>Test authenticated areas of your site by providing login URLs and session cookies. Verify that protected pages behave correctly for logged-in users.</p>
    </div>
</div>

<div class="card mt-3">
    <h2>Why Choose Website Auditor?</h2>
    <div class="feature-grid">
        <div class="feature-card">
            <h3>&#x1F4B0; 100% Free</h3>
            <p>No subscriptions, no page limits, no feature gates. Every audit capability is available to everyone at no cost.</p>
        </div>
        <div class="feature-card">
            <h3>&#x26A1; One-Click Audits</h3>
            <p>Enter a URL, select your test modules, and click Run. Get a comprehensive report in minutes with zero configuration required.</p>
        </div>
        <div class="feature-card">
            <h3>&#x1F4CA; Detailed Reports</h3>
            <p>Every audit generates a structured report with findings organized by severity, module, and page. Export or share results easily.</p>
        </div>
    </div>
</div>

<div class="card mt-3">
    <h2>Frequently Asked Questions</h2>
    <div style="margin-top: 16px;">
        <h3 style="color: var(--accent); margin-bottom: 8px;">What does Website Auditor check?</h3>
        <p class="text-muted">Website Auditor checks page availability, broken links, forms and interactions, security headers, authentication flows, and overall site performance across your entire website.</p>

        <h3 style="color: var(--accent); margin: 24px 0 8px;">Is Website Auditor free?</h3>
        <p class="text-muted">Yes, Website Auditor is completely free with no page limits, no login required, and no feature restrictions.</p>

        <h3 style="color: var(--accent); margin: 24px 0 8px;">How many pages can Website Auditor crawl?</h3>
        <p class="text-muted">You can configure the crawler to check up to hundreds of pages per audit, with adjustable crawl depth, concurrency, and timeout settings.</p>

        <h3 style="color: var(--accent); margin: 24px 0 8px;">Do I need to create an account?</h3>
        <p class="text-muted">No. Website Auditor requires no registration, login, or account creation. Just enter a URL and start auditing.</p>

        <h3 style="color: var(--accent); margin: 24px 0 8px;">How is this different from Semrush or Ahrefs?</h3>
        <p class="text-muted">Unlike Semrush ($140/mo) or Ahrefs ($99/mo), Website Auditor is completely free. It focuses specifically on comprehensive site auditing with chaos/failure testing capabilities that most SEO tools lack.</p>
    </div>
</div>
{% endblock %}'''

with open("templates/features.html", "w") as f:
    f.write(FEATURES_HTML)
print("[OK] templates/features.html created")

# ============================================================
# FIX 3: Create how-it-works.html template
# ============================================================
HOW_IT_WORKS_HTML = r'''{% extends "base.html" %}
{% block title %}How It Works - Website Audit in 3 Steps | Website Auditor{% endblock %}
{% block meta_description %}Learn how Website Auditor works: enter a URL, select test modules, and get a comprehensive audit report. Free website scanning for SEO, security, and performance.{% endblock %}
{% block og_title %}How Website Auditor Works - 3 Simple Steps{% endblock %}
{% block og_description %}Enter a URL, choose your tests, get an instant audit report. Free and easy website scanning.{% endblock %}

{% block content %}
<h2 style="font-size:1.5rem; margin-bottom:24px;">&#x2699;&#xFE0F; How It Works</h2>

<div class="card">
    <h2>Step 1: Enter Your URL</h2>
    <p class="text-muted" style="margin-bottom:16px;">Paste any website URL into the dashboard. Website Auditor accepts any publicly accessible URL&mdash;staging environments, production sites, or localhost for local development.</p>
    <p class="text-muted">Configure optional settings like crawl depth (how many levels deep to scan), max pages to crawl, request timeout, and concurrency level for parallel scanning.</p>
</div>

<div class="card">
    <h2>Step 2: Select Test Modules</h2>
    <p class="text-muted" style="margin-bottom:16px;">Choose which audit modules to run. Each module focuses on a specific aspect of your website:</p>
    <ul style="color: var(--text-muted); list-style: disc; padding-left: 24px; margin-bottom: 16px;">
        <li style="margin-bottom: 8px;"><strong style="color: var(--text);">Page Availability</strong> &mdash; Checks every page for HTTP status codes, redirects, and response times</li>
        <li style="margin-bottom: 8px;"><strong style="color: var(--text);">Broken Links</strong> &mdash; Finds all broken internal and external links across your site</li>
        <li style="margin-bottom: 8px;"><strong style="color: var(--text);">Forms & Interactions</strong> &mdash; Validates forms, buttons, and interactive elements</li>
        <li style="margin-bottom: 8px;"><strong style="color: var(--text);">Chaos / Failure Injection</strong> &mdash; Tests your site's resilience to errors and edge cases</li>
        <li style="margin-bottom: 8px;"><strong style="color: var(--text);">Auth & Sessions</strong> &mdash; Audits authenticated areas with session cookie support</li>
    </ul>
    <p class="text-muted">All modules are selected by default. Deselect any you want to skip.</p>
</div>

<div class="card">
    <h2>Step 3: Review Your Report</h2>
    <p class="text-muted" style="margin-bottom:16px;">After the audit completes, you get a detailed report organized by module. Each finding includes:</p>
    <ul style="color: var(--text-muted); list-style: disc; padding-left: 24px; margin-bottom: 16px;">
        <li style="margin-bottom: 8px;">The specific page URL where the issue was found</li>
        <li style="margin-bottom: 8px;">Severity level (pass, warning, or failure)</li>
        <li style="margin-bottom: 8px;">Description of what was checked and what went wrong</li>
        <li style="margin-bottom: 8px;">Summary statistics across all crawled pages</li>
    </ul>
    <p class="text-muted">Reports are accessible via the Latest Report link in the navigation, or through the REST API for programmatic access.</p>
</div>

<div class="card">
    <h2>Advanced: REST API Access</h2>
    <p class="text-muted" style="margin-bottom:16px;">Website Auditor also offers a JSON API for integrating audits into CI/CD pipelines, monitoring dashboards, or custom workflows:</p>
    <div style="background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 16px; font-family: var(--mono); font-size: 0.85rem; color: var(--accent); overflow-x: auto;">
        <p style="color: var(--text-muted); margin-bottom: 8px;"># Launch an audit via API</p>
        <p>curl -X POST https://website-auditor.io/run \</p>
        <p>&nbsp;&nbsp;-H "Content-Type: application/json" \</p>
        <p>&nbsp;&nbsp;-d '{"url": "https://example.com", "max_pages": 50}'</p>
    </div>
</div>

<div style="text-align:center; margin-top:32px;">
    <a href="/" class="btn btn-primary" style="font-size:1.1rem; padding: 14px 32px;">&#x1F680; Start Your Free Audit Now</a>
</div>
{% endblock %}'''

with open("templates/how_it_works.html", "w") as f:
    f.write(HOW_IT_WORKS_HTML)
print("[OK] templates/how_it_works.html created")

# ============================================================
# FIX 4: Update dashboard.html to add SEO content below the fold
# ============================================================
# Read the existing dashboard template
with open("templates/dashboard.html", "r") as f:
    dashboard = f.read()

# Add SEO content block after endblock content if not already there
seo_block = r'''
{% block seo_content %}
<section class="seo-content">
    <div class="container">
        <h2>Free Website Audit Tool</h2>
        <p>Website Auditor is a comprehensive, free website testing tool that scans your entire site for SEO issues, broken links, security vulnerabilities, form problems, and performance bottlenecks&mdash;all in a single click. Unlike paid tools like Semrush or Ahrefs, there are no page limits, no subscriptions, and no login required.</p>

        <h3>What Website Auditor Checks</h3>
        <div class="feature-grid">
            <div class="feature-card">
                <h3>&#x1F50D; SEO & Broken Links</h3>
                <p>Find broken internal and external links, redirect chains, 404 errors, and orphan pages that hurt your search engine rankings.</p>
            </div>
            <div class="feature-card">
                <h3>&#x1F512; Security & Headers</h3>
                <p>Audit HTTPS configuration, security headers, cookie security (SameSite, Secure, HttpOnly), and common vulnerability indicators.</p>
            </div>
            <div class="feature-card">
                <h3>&#x1F4DD; Forms & Accessibility</h3>
                <p>Validate forms, check for missing labels, test required field validation, and ensure interactive elements are accessible.</p>
            </div>
        </div>

        <h3>How It Works</h3>
        <p>Enter any URL, select which test modules to run, and click the Run button. Website Auditor will crawl your site, test every page, and generate a detailed report organized by issue type and severity. Results are available instantly in your browser or via our REST API for CI/CD integration.</p>

        <p style="margin-top: 24px;"><a href="/features" style="color: var(--accent);">See all features &rarr;</a> &nbsp;&nbsp; <a href="/how-it-works" style="color: var(--accent);">Learn how it works &rarr;</a></p>
    </div>
</section>
{% endblock %}'''

if "seo_content" not in dashboard:
    # Add seo_content block before the last endblock
    dashboard = dashboard.rstrip()
    if dashboard.endswith("{% endblock %}"):
        dashboard = dashboard + "\n" + seo_block
    else:
        dashboard = dashboard + "\n" + seo_block
    with open("templates/dashboard.html", "w") as f:
        f.write(dashboard)
    print("[OK] templates/dashboard.html updated with SEO content section")
else:
    print("[SKIP] templates/dashboard.html already has seo_content block")

# ============================================================
# FIX 5: Add robots.txt, sitemap.xml, features, and how-it-works
#         routes to app.py
# ============================================================
with open("app.py", "r") as f:
    app_py = f.read()

# Add new routes before the if __name__ block
new_routes = '''

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
    xml = '<?xml version="1.0" encoding="UTF-8"?>\\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n'
    for p in pages:
        xml += f'  <url>\\n'
        xml += f'    <loc>{p["loc"]}</loc>\\n'
        xml += f'    <changefreq>{p["changefreq"]}</changefreq>\\n'
        xml += f'    <priority>{p["priority"]}</priority>\\n'
        xml += f'  </url>\\n'
    xml += '</urlset>'
    return Response(xml, mimetype="application/xml")


@app.route("/features")
def features_page():
    return render_template("features.html")


@app.route("/how-it-works")
def how_it_works_page():
    return render_template("how_it_works.html")

'''

if "/robots.txt" not in app_py:
    # Insert before `if __name__`
    insertion_point = app_py.rfind('if __name__')
    if insertion_point > 0:
        app_py = app_py[:insertion_point] + new_routes + "\n" + app_py[insertion_point:]
    else:
        app_py += new_routes

    with open("app.py", "w") as f:
        f.write(app_py)
    print("[OK] app.py updated with robots.txt, sitemap.xml, /features, /how-it-works routes")
else:
    print("[SKIP] app.py already has /robots.txt route")


# ============================================================
# FIX 6: Create a simple OG image placeholder
# ============================================================
os.makedirs("static", exist_ok=True)
# Create a simple SVG as OG image placeholder
og_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#0f172a"/>
  <text x="600" y="280" text-anchor="middle" font-family="Arial, sans-serif" font-size="64" font-weight="bold" fill="#38bdf8">Website Auditor</text>
  <text x="600" y="360" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" fill="#94a3b8">Free Website Audit Tool for SEO, Security &amp; Performance</text>
  <text x="600" y="420" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="#4ade80">No login required &#x2022; No page limits &#x2022; 100% Free</text>
</svg>'''
with open("static/og-image.svg", "w") as f:
    f.write(og_svg)
print("[OK] static/og-image.svg created")

print("\n=== All SEO fixes applied successfully ===")
print("Files modified/created:")
print("  - templates/base.html (rewritten with SEO meta tags)")
print("  - templates/features.html (new)")
print("  - templates/how_it_works.html (new)")
print("  - templates/dashboard.html (added SEO content section)")
print("  - app.py (added robots.txt, sitemap.xml, /features, /how-it-works routes)")
print("  - static/og-image.svg (new)")
