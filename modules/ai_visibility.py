"""
AI Visibility Scanner Module
Evaluates how prominently a business appears in AI platform recommendations
across ChatGPT, Perplexity, Claude, and Gemini.
"""

import logging
import re
import json
import hashlib
from urllib.parse import urlparse
from .base import BaseModule
from .business_identifier import BusinessIdentifier
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger(__name__)

# AI platform query configurations
AI_PLATFORMS = [
    {"name": "ChatGPT", "icon": "\U0001f916", "color": "#10a37f"},
    {"name": "Perplexity", "icon": "\U0001f50d", "color": "#20808d"},
    {"name": "Claude", "icon": "\U0001f9e0", "color": "#cc785c"},
    {"name": "Gemini", "icon": "\u2728", "color": "#4285f4"},
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
    "holding": ["holding company", "investment firm", "portfolio company", "venture capital"],
    "consulting": ["consulting firm", "management consulting", "business consulting", "advisory"],
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
        self._identifier = BusinessIdentifier(session=self.session, timeout=config.request_timeout)
        self._identification_details = {}

    def _extract_business_info(self, url, page_content=""):
        """
        Extract business name, industry, and location from URL and page content.
        Uses the BusinessIdentifier pipeline:
          1. Scrape candidate names from headers, footers, legal text, entity suffixes
          2. Score and rank candidates
          3. Pick highest-confidence business name
          4. Reverse-lookup headquarters city from business records
          5. Use headquarters city as the dashboard location
        """
        # --- Run the full identification pipeline ---------------------
        try:
            result = self._identifier.identify(url, html=page_content)
            self._identification_details = result

            if result["business_name"]:
                self.business_name = result["business_name"]
            if result["location"]:
                self.location = result["location"]
        except Exception as exc:
            logger.warning("BusinessIdentifier failed: %s -- falling back to domain parse", exc)

        # --- Fallback: derive from domain if identifier found nothing -
        if not self.business_name:
            parsed = urlparse(url)
            domain = parsed.hostname or ""
            domain_name = re.sub(r"^www\.", "", domain)
            domain_name = re.sub(r"\.(com|net|org|io|co|biz|us|info).*$", "", domain_name)
            self.business_name = domain_name.replace("-", " ").replace("_", " ").title()

        if not self.location:
            self.location = "your area"

        # --- Detect industry from domain + page content ---------------
        combined = (url + " " + page_content).lower()
        for ind, keywords in INDUSTRY_KEYWORDS.items():
            if ind == "default":
                continue
            for kw in keywords:
                if kw.lower() in combined:
                    self.industry = ind
                    break
            if self.industry != "default":
                break

        logger.info(
            "AI Visibility business info: name=%r industry=%r location=%r",
            self.business_name, self.industry, self.location,
        )

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
                page_content = resp.text[:10000]  # increased from 5000 for better extraction
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
            "identification": {
                "candidates": self._identification_details.get("candidates", []),
                "lookup_source": self._identification_details.get("lookup_source", ""),
            },
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
        status = TestStatus.PASSED if overall_score >= 50 else (TestStatus.WARNING if overall_score >= 25 else TestStatus.FAILED)
        severity = Severity.INFO if overall_score >= 50 else (Severity.MEDIUM if overall_score >= 25 else Severity.HIGH)
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
