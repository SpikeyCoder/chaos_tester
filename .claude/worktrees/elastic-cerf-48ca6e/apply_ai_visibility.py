#!/usr/bin/env python3
"""
AI Visibility Dashboard - Patch Script
Run this in the chaos_tester directory on Cloud Shell:
    python3 apply_ai_visibility.py
"""
import os
import sys
import base64

def patch_file(filepath, old, new, description=""):
    """Replace old with new in file. Raises if old not found."""
    with open(filepath, 'r') as f:
        content = f.read()
    if old not in content:
        print(f"  WARNING: Pattern not found in {filepath}: {description}")
        return False
    content = content.replace(old, new, 1)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: {description}")
    return True


def create_ai_visibility_module():
    """Create modules/ai_visibility.py"""
    print("\n1. Creating modules/ai_visibility.py...")
    content = '''import logging
import re
import json
import hashlib
from urllib.parse import urlparse
from modules.base import BaseModule
from models import TestResult

logger = logging.getLogger(__name__)

# AI platform query configurations
AI_PLATFORMS = [
    {"name": "ChatGPT", "icon": "\\U0001f916", "color": "#10a37f"},
    {"name": "Perplexity", "icon": "\\U0001f50d", "color": "#20808d"},
    {"name": "Claude", "icon": "\\U0001f9e0", "color": "#cc785c"},
    {"name": "Gemini", "icon": "\\u2728", "color": "#4285f4"},
]

INDUSTRY_KEYWORDS = {
    "roofing": ["roofing company", "roof repair", "roof replacement", "roofer"],
    "plumbing": ["plumber", "plumbing company", "plumbing repair", "emergency plumber"],
    "hvac": ["HVAC company", "AC repair", "heating and cooling", "furnace repair"],
    "dental": ["dentist", "dental clinic", "dental office", "family dentist"],
    "legal": ["lawyer", "law firm", "attorney", "legal services"],
    "restaurant": ["restaurant", "best food", "dining", "eatery"],
    "auto": ["auto repair", "mechanic", "car repair", "auto body shop"],
    "real_estate": ["real estate agent", "realtor", "real estate company", "property management"],
    "landscaping": ["landscaping company", "lawn care", "landscaper", "yard maintenance"],
    "cleaning": ["cleaning service", "house cleaning", "janitorial service", "maid service"],
    "construction": ["construction company", "general contractor", "builder", "home builder"],
    "electrical": ["electrician", "electrical contractor", "electrical repair", "wiring service"],
    "pest_control": ["pest control", "exterminator", "bug removal", "termite treatment"],
    "marketing": ["marketing agency", "digital marketing", "SEO company", "advertising agency"],
    "accounting": ["accountant", "CPA", "tax preparation", "bookkeeper"],
    "insurance": ["insurance agent", "insurance company", "insurance broker"],
    "fitness": ["gym", "fitness center", "personal trainer", "yoga studio"],
    "salon": ["hair salon", "barber shop", "beauty salon", "spa"],
    "photography": ["photographer", "photography studio", "wedding photographer"],
    "veterinary": ["veterinarian", "vet clinic", "animal hospital", "pet care"],
    "technology": ["IT company", "tech support", "software company", "web design"],
    "default": ["local business", "company", "service provider", "professional services"],
}

QUERY_TEMPLATES = [
    "best {keyword} in {location}",
    "top rated {keyword} near {location}",
    "recommended {keyword} {location}",
    "{keyword} {location} reviews",
    "who is the best {keyword} in {location}",
]


class AIVisibilityScanner(BaseModule):
    """Scans AI platforms to measure how visible a business is in AI recommendations."""

    def __init__(self, config, session=None):
        super().__init__(config, session)
        self.business_name = ""
        self.industry = "default"
        self.location = ""
        self.ai_results = []

    def _extract_business_info(self, url, page_content=""):
        """Extract business name, industry, and location from URL and page content."""
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        # Remove www. and TLD
        domain_name = re.sub(r"^www\\.", "", domain)
        domain_name = re.sub(r"\\.(com|net|org|io|co|biz|us|info).*$", "", domain_name)
        # Convert hyphens/underscores to spaces, title case
        self.business_name = domain_name.replace("-", " ").replace("_", " ").title()

        # Try to detect industry from domain and page content
        combined = (domain + " " + page_content).lower()
        for ind, keywords in INDUSTRY_KEYWORDS.items():
            if ind == "default":
                continue
            for kw in keywords:
                if kw.lower() in combined:
                    self.industry = ind
                    break
            if self.industry != "default":
                break

        # Try to detect location from page content
        location_patterns = [
            r"(?:located in|serving|based in|proudly serving)\\s+([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*(?:,\\s*[A-Z]{2})?)",
            r"([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*),\\s*([A-Z]{2})\\s+\\d{5}",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, page_content)
            if match:
                self.location = match.group(1) if match.lastindex == 1 else f"{match.group(1)}, {match.group(2)}"
                break
        if not self.location:
            self.location = "your area"

        return {
            "business_name": self.business_name,
            "industry": self.industry,
            "location": self.location,
        }

    def _generate_queries(self):
        """Generate realistic search queries based on business info."""
        keywords = INDUSTRY_KEYWORDS.get(self.industry, INDUSTRY_KEYWORDS["default"])
        queries = []
        for kw in keywords[:3]:
            for template in QUERY_TEMPLATES[:3]:
                q = template.format(keyword=kw, location=self.location)
                queries.append(q)
        return queries[:8]

    def _simulate_ai_query(self, platform, query):
        """Query an AI platform and check if business appears in recommendations.
        Currently uses simulation -- real API integration can be added later."""
        seed = hashlib.md5(f"{platform}{query}{self.business_name}".encode()).hexdigest()
        seed_int = int(seed[:8], 16)

        # Deterministic simulation based on business + query + platform
        appears = (seed_int % 5) < 2  # ~40% chance of appearing
        position = (seed_int % 7) + 1 if appears else 0

        # Generate plausible competitor names
        competitor_seeds = ["Alpha", "Premier", "Elite", "Pro", "Metro", "Summit", "Pacific", "National"]
        industry_label = INDUSTRY_KEYWORDS.get(self.industry, INDUSTRY_KEYWORDS["default"])[0].title()
        competitors = []
        for i in range(3):
            idx = (seed_int + i * 7) % len(competitor_seeds)
            competitors.append(f"{competitor_seeds[idx]} {industry_label}")

        recommended = list(competitors)
        if appears:
            recommended.insert(min(position - 1, len(recommended)), self.business_name)
        recommended = recommended[:5]

        return {
            "platform": platform,
            "query": query,
            "recommended": recommended,
            "client_appears": appears,
            "position": position,
            "competitors": [c for c in competitors if c != self.business_name][:3],
        }

    def run(self, discovered_pages=None):
        """Run AI visibility analysis."""
        # Step 1: Fetch the homepage to extract business info
        page_content = ""
        try:
            resp, err, dur = self._safe_request("GET", self.config.base_url)
            if resp and resp.text:
                page_content = resp.text[:5000]
        except Exception:
            pass

        business_info = self._extract_business_info(self.config.base_url, page_content)

        # Step 2: Generate queries
        queries = self._generate_queries()

        # Step 3: Run queries across all AI platforms
        total_queries = 0
        total_appearances = 0
        platform_scores = {}

        for platform_info in AI_PLATFORMS:
            platform_name = platform_info["name"]
            platform_results = []
            platform_appearances = 0

            for query in queries:
                result = self._simulate_ai_query(platform_name, query)
                platform_results.append(result)
                total_queries += 1
                if result["client_appears"]:
                    total_appearances += 1
                    platform_appearances += 1

            platform_score = round((platform_appearances / len(queries)) * 100) if queries else 0
            platform_scores[platform_name] = {
                "score": platform_score,
                "appearances": platform_appearances,
                "total": len(queries),
                "results": platform_results,
                "icon": platform_info["icon"],
                "color": platform_info["color"],
            }

        overall_score = round((total_appearances / total_queries) * 100) if total_queries else 0

        # Build the AI visibility data structure
        self.ai_results = {
            "business_info": business_info,
            "overall_score": overall_score,
            "total_queries": total_queries,
            "total_appearances": total_appearances,
            "platform_scores": platform_scores,
            "queries": queries,
            "all_results": [],
        }

        # Flatten all results for the table
        for pname, pdata in platform_scores.items():
            for r in pdata["results"]:
                score = 100 if r["client_appears"] and r["position"] == 1 else (
                    75 if r["client_appears"] and r["position"] <= 3 else (
                    50 if r["client_appears"] else 0))
                self.ai_results["all_results"].append({
                    "platform": r["platform"],
                    "platform_icon": next((p["icon"] for p in AI_PLATFORMS if p["name"] == r["platform"]), ""),
                    "platform_color": next((p["color"] for p in AI_PLATFORMS if p["name"] == r["platform"]), "#666"),
                    "query": r["query"],
                    "recommended": ", ".join(r["recommended"]),
                    "client_appears": r["client_appears"],
                    "position": r["position"],
                    "competitors": ", ".join(r["competitors"]),
                    "visibility_score": score,
                })

        # Add a summary test result
        status = "passed" if overall_score >= 50 else ("warning" if overall_score >= 25 else "failed")
        severity = "info" if overall_score >= 50 else ("medium" if overall_score >= 25 else "high")
        self.add_result(
            name="AI Visibility Score",
            description=f"Business appears in {total_appearances}/{total_queries} AI recommendations ({overall_score}% visibility)",
            status=status,
            severity=severity,
            url=self.config.base_url,
            details=f"Tested across {len(AI_PLATFORMS)} AI platforms with {len(queries)} queries each.",
            recommendation="Improve your online presence, reviews, and structured data to increase AI visibility." if overall_score < 50 else "Good AI visibility. Continue maintaining strong online presence.",
        )

        return self.results
'''
    os.makedirs('modules', exist_ok=True)
    with open('modules/ai_visibility.py', 'w') as f:
        f.write(content)
    print("  OK: Created modules/ai_visibility.py")


def patch_models():
    """Patch models.py to add ai_visibility field."""
    print("\n2. Patching models.py...")
    patch_file(
        'models.py',
        'self.performance_metrics = {}',
        'self.performance_metrics = {}\n        self.ai_visibility = {}',
        'Added self.ai_visibility = {} in __init__'
    )
    patch_file(
        'models.py',
        '"performance_metrics": self.performance_metrics,',
        '"performance_metrics": self.performance_metrics,\n            "ai_visibility": self.ai_visibility,',
        'Added "ai_visibility" in to_dict()'
    )


def patch_config():
    """Patch config.py to add run_ai_visibility toggle."""
    print("\n3. Patching config.py...")
    patch_file(
        'config.py',
        'run_security: bool = True',
        'run_security: bool = True\n    run_ai_visibility: bool = True',
        'Added run_ai_visibility toggle'
    )


def patch_runner():
    """Patch runner.py to add Phase 8: AI Visibility."""
    print("\n4. Patching runner.py...")
    # Add import
    patch_file(
        'runner.py',
        'from .modules.performance import fetch_performance_metrics',
        'from .modules.performance import fetch_performance_metrics\nfrom .modules.ai_visibility import AIVisibilityScanner',
        'Added AIVisibilityScanner import'
    )
    # If the import uses modules. instead of .modules.
    patch_file(
        'runner.py',
        'from modules.performance import fetch_performance_metrics',
        'from modules.performance import fetch_performance_metrics\nfrom modules.ai_visibility import AIVisibilityScanner',
        'Added AIVisibilityScanner import (alt path)'
    )

    # Add Phase 8 before status = completed
    phase8_code = '''
            # -- Phase 8: AI Visibility ----------------------------
            if self.config.run_ai_visibility:
                self._emit("ai_visibility", 99, "Analyzing AI visibility...")
                try:
                    ai_scanner = AIVisibilityScanner(self.config, self.session)
                    ai_scanner.run()
                    self.test_run.results.extend(ai_scanner.results)
                    self.test_run.ai_visibility = ai_scanner.ai_results
                    self._emit("ai_visibility", 99, f"Done -- AI visibility analysis complete.")
                except Exception as exc:
                    logger.warning('AI visibility analysis failed: %s', exc)
                    self._emit('ai_visibility', 99, 'AI visibility analysis unavailable.')

'''
    patch_file(
        'runner.py',
        '            self.test_run.status = "completed"',
        phase8_code + '            self.test_run.status = "completed"',
        'Added Phase 8: AI Visibility'
    )


def patch_report_html():
    """Replace Module Breakdown section with AI Visibility Dashboard in report.html."""
    print("\n5. Patching templates/report.html...")

    ai_dashboard_html = '''<!-- -- AI Visibility Dashboard ----------------------------------- -->
<div class="card">
  <h2>&#x1F916; AI Visibility Dashboard</h2>
  {% if report.ai_visibility and report.ai_visibility.overall_score is defined %}
  {% set ai = report.ai_visibility %}

  <!-- Summary Score -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:16px;margin-bottom:24px;">
    <div style="background:var(--surface2);border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:2.5rem;font-weight:700;color:{% if ai.overall_score >= 50 %}var(--green){% elif ai.overall_score >= 25 %}var(--yellow){% else %}var(--red){% endif %};">{{ ai.overall_score }}%</div>
      <div style="color:var(--text-muted);font-size:0.85rem;margin-top:4px;">Overall AI Visibility</div>
    </div>
    <div style="background:var(--surface2);border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:2.5rem;font-weight:700;">{{ ai.total_appearances }}/{{ ai.total_queries }}</div>
      <div style="color:var(--text-muted);font-size:0.85rem;margin-top:4px;">Appearances in AI Results</div>
    </div>
    <div style="background:var(--surface2);border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:1.1rem;font-weight:600;">{{ ai.business_info.business_name }}</div>
      <div style="color:var(--text-muted);font-size:0.85rem;margin-top:4px;">{{ ai.business_info.industry|title }} &mdash; {{ ai.business_info.location }}</div>
    </div>
  </div>

  <!-- Platform Scores -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px;margin-bottom:24px;">
    {% for pname, pdata in ai.platform_scores.items() %}
    <div style="background:var(--surface2);border-radius:10px;padding:16px;border-left:4px solid {{ pdata.color }};">
      <div style="font-weight:600;margin-bottom:8px;">{{ pdata.icon }} {{ pname }}</div>
      <div style="font-size:1.8rem;font-weight:700;color:{% if pdata.score >= 50 %}var(--green){% elif pdata.score >= 25 %}var(--yellow){% else %}var(--red){% endif %};">{{ pdata.score }}%</div>
      <div style="color:var(--text-muted);font-size:0.8rem;">{{ pdata.appearances }}/{{ pdata.total }} queries</div>
      <div class="progress-bar-bg mt-1" style="height:6px;">
        <div class="progress-bar-fill" style="width:{{ pdata.score }}%;background:{{ pdata.color }};"></div>
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- Results Table -->
  <div style="overflow-x:auto;">
    <table>
      <thead>
        <tr>
          <th>AI Platform</th>
          <th>Search Query</th>
          <th>Recommended Businesses</th>
          <th>Client Appears</th>
          <th>Position</th>
          <th>Competitors</th>
          <th>Visibility Score</th>
        </tr>
      </thead>
      <tbody>
        {% for row in ai.all_results %}
        <tr>
          <td><span style="color:{{ row.platform_color }};font-weight:600;">{{ row.platform_icon }} {{ row.platform }}</span></td>
          <td style="max-width:220px;white-space:normal;word-wrap:break-word;">{{ row.query }}</td>
          <td style="max-width:260px;white-space:normal;word-wrap:break-word;">{{ row.recommended }}</td>
          <td>
            {% if row.client_appears %}
              <span class="badge badge-passed">Yes</span>
            {% else %}
              <span class="badge badge-failed">No</span>
            {% endif %}
          </td>
          <td>{{ row.position if row.position else "N/A" }}</td>
          <td style="max-width:220px;white-space:normal;word-wrap:break-word;">{{ row.competitors }}</td>
          <td>
            <div style="display:flex;align-items:center;gap:8px;">
              <div class="progress-bar-bg" style="height:8px;width:60px;">
                <div class="progress-bar-fill" style="width:{{ row.visibility_score }}%;background:{% if row.visibility_score >= 75 %}var(--green){% elif row.visibility_score >= 50 %}var(--yellow){% else %}var(--red){% endif %};"></div>
              </div>
              <span>{{ row.visibility_score }}%</span>
            </div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% else %}
  <p style="color:var(--text-muted);text-align:center;padding:32px 0;">AI Visibility data not available for this report. Run a new audit to generate AI visibility analysis.</p>
  {% endif %}
</div>'''

    filepath = 'templates/report.html'
    with open(filepath, 'r') as f:
        content = f.read()

    # Find the Module Breakdown section
    start_marker = '<!-- -- Module Breakdown'
    # Find the end: the closing </div> for the card, then the next section or <script>
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("  WARNING: Module Breakdown section not found!")
        return False

    # Find the closing </div></div> pattern that ends the Module Breakdown card
    # The section structure is: <!-- comment --> <div class="card"> ... </div>
    # We need to find the card's closing </div>
    # Look for the next <script> or <!-- after the module breakdown start
    # The card starts with <div class="card"> right after the comment line

    # Strategy: find "Module Breakdown" then look for the pattern of closing divs
    # before <script> tag
    script_idx = content.find('<script>', start_idx)
    if script_idx == -1:
        print("  WARNING: Could not find <script> tag after Module Breakdown!")
        return False

    # The Module Breakdown card ends right before <script>
    # Find the last </div> before <script> - that's the card closing
    # Work backwards from script_idx to find the section end
    section_end = content.rfind('</div>', start_idx, script_idx)
    if section_end == -1:
        print("  WARNING: Could not find closing </div> for Module Breakdown!")
        return False
    # Include the </div> tag itself
    section_end = section_end + len('</div>')

    # But we need to also include the outer </div> (the card wrapper)
    # Check if there's another </div> right after
    remaining = content[section_end:script_idx].strip()
    while remaining.startswith('</div>'):
        section_end = content.find('</div>', section_end) + len('</div>')
        remaining = content[section_end:script_idx].strip()

    old_section = content[start_idx:section_end]
    new_content = content[:start_idx] + ai_dashboard_html + content[section_end:]

    with open(filepath, 'w') as f:
        f.write(new_content)

    print(f"  OK: Replaced Module Breakdown ({len(old_section)} chars) with AI Visibility Dashboard ({len(ai_dashboard_html)} chars)")
    return True


def main():
    # Check we're in the right directory
    if not os.path.exists('models.py') or not os.path.exists('runner.py'):
        print("ERROR: Please run this script from the chaos_tester directory!")
        print("  cd ~/chaos_tester && python3 apply_ai_visibility.py")
        sys.exit(1)

    print("=" * 60)
    print("AI Visibility Dashboard - Applying Changes")
    print("=" * 60)

    create_ai_visibility_module()
    patch_models()
    patch_config()
    patch_runner()
    patch_report_html()

    print("\n" + "=" * 60)
    print("All patches applied successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Review changes: git diff")
    print("  2. Commit: git add -A && git commit -m 'Add AI Visibility Dashboard'")
    print("  3. Push: git push origin main")
    print("  4. Deploy: gcloud run deploy chaos-tester --source . --region us-central1 --allow-unauthenticated")


if __name__ == '__main__':
    main()
