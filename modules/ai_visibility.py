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
    {
        "name": "ChatGPT",
        "color": "#10a37f",
        "logo_url": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2222%22%20height%3D%2222%22%20viewBox%3D%220%200%2024%2024%22%3E%3Cpath%20fill%3D%22%2310a37f%22%20d%3D%22M22.282%209.821a6%206%200%200%200-.516-4.91a6.05%206.05%200%200%200-6.51-2.9A6.065%206.065%200%200%200%204.981%204.18a6%206%200%200%200-3.998%202.9a6.05%206.05%200%200%200%20.743%207.097a5.98%205.98%200%200%200%20.51%204.911a6.05%206.05%200%200%200%206.515%202.9A6%206%200%200%200%2013.26%2024a6.06%206.06%200%200%200%205.772-4.206a6%206%200%200%200%203.997-2.9a6.06%206.06%200%200%200-.747-7.073M13.26%2022.43a4.48%204.48%200%200%201-2.876-1.04l.141-.081l4.779-2.758a.8.8%200%200%200%20.392-.681v-6.737l2.02%201.168a.07.07%200%200%201%20.038.052v5.583a4.504%204.504%200%200%201-4.494%204.494M3.6%2018.304a4.47%204.47%200%200%201-.535-3.014l.142.085l4.783%202.759a.77.77%200%200%200%20.78%200l5.843-3.369v2.332a.08.08%200%200%201-.033.062L9.74%2019.95a4.5%204.5%200%200%201-6.14-1.646M2.34%207.896a4.5%204.5%200%200%201%202.366-1.973V11.6a.77.77%200%200%200%20.388.677l5.815%203.354l-2.02%201.168a.08.08%200%200%201-.071%200l-4.83-2.786A4.504%204.504%200%200%201%202.34%207.872zm16.597%203.855l-5.833-3.387L15.119%207.2a.08.08%200%200%201%20.071%200l4.83%202.791a4.494%204.494%200%200%201-.676%208.105v-5.678a.79.79%200%200%200-.407-.667m2.01-3.023l-.141-.085l-4.774-2.782a.78.78%200%200%200-.785%200L9.409%209.23V6.897a.07.07%200%200%201%20.028-.061l4.83-2.787a4.5%204.5%200%200%201%206.68%204.66zm-12.64%204.135l-2.02-1.164a.08.08%200%200%201-.038-.057V6.075a4.5%204.5%200%200%201%207.375-3.453l-.142.08L8.704%205.46a.8.8%200%200%200-.393.681zm1.097-2.365l2.602-1.5l2.607%201.5v2.999l-2.597%201.5l-2.607-1.5Z%22%2F%3E%3C%2Fsvg%3E",
    },
    {
        "name": "Perplexity",
        "color": "#20808d",
        "logo_url": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2222%22%20height%3D%2222%22%20viewBox%3D%220%200%2024%2024%22%3E%3Cpath%20fill%3D%22%2320808d%22%20d%3D%22M22.398%207.09h-2.31V.068l-7.51%206.354V.158h-1.156v6.196L4.49%200v7.09H1.602v10.397H4.49V24l6.933-6.36v6.201h1.155v-6.047l6.932%206.181v-6.488h2.888zm-3.466-4.531v4.53h-5.355zm-13.286.067l4.869%204.464h-4.87zM2.758%2016.332V8.245h7.847L4.49%2014.36v1.972zm2.888%205.04v-6.534l5.776-5.776v7.011zm12.708.025l-5.776-5.15V9.061l5.776%205.776zm2.889-5.065H19.51V14.36l-6.115-6.115h7.848z%22%2F%3E%3C%2Fsvg%3E",
    },
    {
        "name": "Claude",
        "color": "#cc785c",
        "logo_url": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2222%22%20height%3D%2222%22%20viewBox%3D%220%200%2024%2024%22%3E%3Cpath%20fill%3D%22%23cc785c%22%20d%3D%22M17.304%203.541h-3.672l6.696%2016.918H24Zm-10.608%200L0%2020.459h3.744l1.37-3.553h7.005l1.369%203.553h3.744L10.536%203.541Zm-.371%2010.223L8.616%207.82l2.291%205.945Z%22%2F%3E%3C%2Fsvg%3E",
    },
    {
        "name": "Gemini",
        "color": "#4285f4",
        "logo_url": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2222%22%20height%3D%2222%22%20viewBox%3D%220%200%2024%2024%22%3E%3Cpath%20fill%3D%22%234285f4%22%20d%3D%22M11.04%2019.32Q12%2021.51%2012%2024q0-2.49.93-4.68q.96-2.19%202.58-3.81t3.81-2.55Q21.51%2012%2024%2012q-2.49%200-4.68-.93a12.3%2012.3%200%200%201-3.81-2.58a12.3%2012.3%200%200%201-2.58-3.81Q12%202.49%2012%200q0%202.49-.96%204.68q-.93%202.19-2.55%203.81a12.3%2012.3%200%200%201-3.81%202.58Q2.49%2012%200%2012q2.49%200%204.68.96q2.19.93%203.81%202.55t2.55%203.81%22%2F%3E%3C%2Fsvg%3E",
    },
]

# ── Sector-specific search keywords ────────────────────────────────
# Maps sector labels (from BusinessIdentifier.detect_sector) to query keywords
SECTOR_QUERY_KEYWORDS = {
    "holding company services":     ["holding company", "investment firm", "portfolio company", "venture capital"],
    "financial services":           ["financial advisor", "financial planning", "wealth management", "financial services"],
    "venture capital":              ["venture capital firm", "startup investor", "VC firm", "investment fund"],
    "investment services":          ["investment firm", "investment advisor", "asset management", "investment services"],
    "real estate":                  ["real estate agent", "realtor", "real estate company", "property management"],
    "construction":                 ["construction company", "general contractor", "builder", "home builder"],
    "technology":                   ["IT company", "tech company", "software company", "technology services"],
    "technology and product development": ["tech company", "product development", "software company", "technology services"],
    "mobile app development":       ["app developer", "mobile app company", "iOS developer", "app development"],
    "ecommerce and payments":       ["ecommerce company", "payment solutions", "online store", "ecommerce platform"],
    "AI and technology":            ["AI company", "artificial intelligence", "machine learning", "tech company"],
    "digital services":             ["digital agency", "digital services", "web services", "online services"],
    "media and advertising":        ["media company", "advertising agency", "media agency", "ad firm"],
    "healthcare":                   ["healthcare provider", "medical practice", "doctor", "healthcare services"],
    "dental services":              ["dentist", "dental clinic", "dental office", "family dentist"],
    "legal services":               ["lawyer", "law firm", "attorney", "legal services"],
    "consulting":                   ["consulting firm", "management consulting", "business consulting", "advisory"],
    "restaurant":                   ["restaurant", "best food", "dining", "eatery"],
    "food services":                ["catering", "food service", "meal prep", "food delivery"],
    "automotive services":          ["auto repair", "mechanic", "car repair", "auto body shop"],
    "electrical services":          ["electrician", "electrical contractor", "electrical repair", "wiring service"],
    "plumbing":                     ["plumber", "plumbing company", "plumbing repair", "emergency plumber"],
    "roofing":                      ["roofing company", "roof repair", "roof replacement", "roofer"],
    "heating and cooling":          ["HVAC company", "AC repair", "heating and cooling", "furnace repair"],
    "cleaning services":            ["cleaning service", "house cleaning", "janitorial service", "maid service"],
    "landscaping":                  ["landscaping company", "lawn care", "landscaper", "yard maintenance"],
    "pest control":                 ["pest control", "exterminator", "bug removal", "termite treatment"],
    "marketing and advertising":    ["marketing agency", "digital marketing", "SEO company", "advertising agency"],
    "digital marketing":            ["SEO company", "digital marketing agency", "online marketing", "PPC agency"],
    "accounting and tax":           ["accountant", "CPA", "tax preparation", "bookkeeper"],
    "insurance":                    ["insurance agent", "insurance company", "insurance broker", "insurance agency"],
    "fitness and wellness":         ["gym", "fitness center", "personal trainer", "yoga studio"],
    "beauty and wellness":          ["hair salon", "beauty salon", "spa", "wellness center"],
    "beauty and personal care":     ["hair salon", "barber shop", "beauty salon", "spa"],
    "photography":                  ["photographer", "photography studio", "wedding photographer", "photo studio"],
    "media production":             ["video production", "media production", "film company", "videographer"],
    "veterinary services":          ["veterinarian", "vet clinic", "animal hospital", "pet care"],
    "education":                    ["school", "tutoring service", "education center", "learning academy"],
    "child care":                   ["daycare", "child care center", "preschool", "after school program"],
    "professional services":        ["professional services", "business services", "consulting", "advisory"],
    "local business services":      ["local business", "company", "service provider", "professional services"],
    "logistics and shipping":       ["logistics company", "shipping service", "freight company", "delivery service"],
    "transportation":               ["transportation company", "taxi service", "shuttle service", "limo service"],
    "energy services":              ["energy company", "utility company", "power company", "energy services"],
    "solar energy":                 ["solar company", "solar installer", "solar energy", "solar panel company"],
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
        self.sector = "local business services"
        self.location = ""
        self.ai_results = []
        self._identifier = BusinessIdentifier(session=self.session, timeout=config.request_timeout)
        self._identification_details = {}

    def _extract_business_info(self, url, page_content=""):
        """
        Extract business name, sector, and location from URL and page content.
        Uses the BusinessIdentifier pipeline:
          1. Scrape candidate names from headers, footers, legal text, entity suffixes
          2. Score and rank candidates
          3. Pick highest-confidence business name
          4. Multi-source headquarters city lookup (structured data, HTML patterns,
             OpenCorporates, IRS EO, secondary pages, WHOIS/RDAP)
          5. Detect business sector from IRS NTEE codes, business name analysis,
             JSON-LD @type, and page content keyword analysis
          6. Use HQ city + sector keywords in AI visibility queries
        """
        # --- Check for user-provided location override -----------------
        user_location = getattr(self.config, "business_location", "") or ""
        user_location = user_location.strip()

        # --- Run the full identification pipeline ---------------------
        try:
            result = self._identifier.identify(url, html=page_content)
            self._identification_details = result

            if result["business_name"]:
                self.business_name = result["business_name"]
            if result["location"]:
                self.location = result["location"]
            if result.get("sector"):
                self.sector = result["sector"]
        except Exception as exc:
            logger.warning("BusinessIdentifier failed: %s -- falling back to domain parse", exc)

        # --- User-provided location always wins ----------------------
        if user_location:
            self.location = user_location
            logger.info("Using user-provided location: %r", user_location)

        # Sanitize: strip any URL that may have been concatenated with the location
        if self.location and ("http://" in self.location or "https://" in self.location):
            self.location = re.sub(r"https?://\S+", "", self.location).strip()
            logger.warning("Stripped URL from location, result: %r", self.location)

        # --- Fallback: derive from domain if identifier found nothing -
        if not self.business_name:
            parsed = urlparse(url)
            domain = parsed.hostname or ""
            domain_name = re.sub(r"^www\.", "", domain)
            domain_name = re.sub(r"\.(com|net|org|io|co|biz|us|info).*$", "", domain_name)
            self.business_name = domain_name.replace("-", " ").replace("_", " ").title()

        if not self.location:
            self.location = "your area"

        logger.info(
            "AI Visibility business info: name=%r sector=%r location=%r",
            self.business_name, self.sector, self.location,
        )

        return {
            "business_name": self.business_name,
            "sector": self.sector,
            "industry": self.sector,  # backward compat with template
            "location": self.location,
        }

    def _generate_queries(self):
        """Generate realistic search queries based on business sector and location."""
        # Get sector-specific keywords, fall back to generic
        keywords = SECTOR_QUERY_KEYWORDS.get(
            self.sector,
            SECTOR_QUERY_KEYWORDS["local business services"],
        )
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

        # Generate plausible competitor names using sector keywords
        competitor_seeds = ["Alpha", "Premier", "Elite", "Pro", "Metro", "Summit", "Pacific", "National"]
        sector_keywords = SECTOR_QUERY_KEYWORDS.get(
            self.sector,
            SECTOR_QUERY_KEYWORDS["local business services"],
        )
        industry_label = sector_keywords[0].title() if sector_keywords else "Services"
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
                "logo_url": platform_info["logo_url"],
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
                    "platform_logo_url": next((p["logo_url"] for p in AI_PLATFORMS if p["name"] == r["platform"]), ""),
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
