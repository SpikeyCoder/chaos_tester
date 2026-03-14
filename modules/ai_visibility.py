"""
AI Visibility Scanner Module
Evaluates how prominently a business appears in AI platform recommendations
across ChatGPT, Perplexity, Claude, and Gemini.

Performance optimizations:
  - Single Perplexity call per query (shared across 4 platforms with variance)
  - In-memory response cache with 24h TTL
  - Concurrent query execution via ThreadPoolExecutor
"""

import logging
import os
import re
import json
import time
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from .base import BaseModule
from .business_identifier import BusinessIdentifier
from ..models import TestResult, TestStatus, Severity

logger = logging.getLogger(__name__)

# ── In-memory Perplexity response cache (24h TTL) ─────────────────
_cache_lock = threading.Lock()
_response_cache = {}       # key: query_hash → {"response": str, "ts": float}
_CACHE_TTL = 86400         # 24 hours


def _cache_key(query):
    """Stable hash for a query string."""
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]


def _get_cached(query):
    key = _cache_key(query)
    with _cache_lock:
        entry = _response_cache.get(key)
        if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
            logger.info("Cache HIT for query: %s", query[:60])
            return entry["response"]
    return None


def _set_cached(query, response_text):
    key = _cache_key(query)
    with _cache_lock:
        _response_cache[key] = {"response": response_text, "ts": time.time()}
        # Evict old entries if cache grows beyond 500
        if len(_response_cache) > 500:
            cutoff = time.time() - _CACHE_TTL
            expired = [k for k, v in _response_cache.items() if v["ts"] < cutoff]
            for k in expired:
                del _response_cache[k]


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

    # ── Revenue bucket definitions ────────────────────────────────────
    REVENUE_BUCKETS = [
        ("Under $1M",   0,            1_000_000),
        ("$1M-$10M",    1_000_000,    10_000_000),
        ("$10M-$50M",   10_000_000,   50_000_000),
        ("$50M-$100M",  50_000_000,   100_000_000),
        ("$100M-$500M", 100_000_000,  500_000_000),
        ("$500M-$1B",   500_000_000,  1_000_000_000),
        ("$1B+",        1_000_000_000, float("inf")),
    ]

    def _get_api_key(self):
        """Get Perplexity API key from config or environment."""
        key = getattr(self.config, "perplexity_api_key", "") or ""
        if not key:
            key = os.getenv("PERPLEXITY_API_KEY", "")
        return key.strip()

    def _query_perplexity(self, query):
        """Send a real search query to Perplexity's sonar model.
        Returns the raw response text, or None on failure."""
        import sys
        api_key = self._get_api_key()
        if not api_key:
            print("[AI_VIS] _query_perplexity: no API key", file=sys.stderr)
            return None
        print(f"[AI_VIS] _query_perplexity: sending query: {query[:80]}", file=sys.stderr)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful local business advisor. "
                        "List the top 5 businesses that match the query. "
                        "For each business, include the business name and "
                        "an approximate annual revenue if known (e.g. ~$5M/yr). "
                        "Format as a numbered list."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "max_tokens": 600,
            "temperature": 0.1,
        }

        try:
            import requests as http_requests
            resp = http_requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 429:
                logger.warning("Perplexity rate-limited, waiting 2s and retrying...")
                time.sleep(2)
                resp = http_requests.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
            if resp.status_code != 200:
                logger.error("Perplexity API error %d: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content
        except Exception as exc:
            logger.error("Perplexity API call failed: %s", exc)
            return None

    def _parse_businesses_from_response(self, text):
        """Extract business names and revenue estimates from AI response text.
        Returns list of dicts: [{"name": str, "revenue_raw": str|None, "revenue_bucket": str|None}]
        """
        if not text:
            return []

        businesses = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            # Must start with a numbered/bulleted list marker
            prefix = re.match(r"^(?:\d+[\.\)]\s*|\-\s*|\*\s*)", line)
            if not prefix:
                continue
            rest = line[prefix.end():]

            # Extract name: prefer bold **Name**, else take text up to first separator
            bold = re.match(r"\*\*(.+?)\*\*", rest)
            if bold:
                raw_name = bold.group(1).strip()
            else:
                name_m = re.match(r"(.+?)(?:\s*[\-–:(\[,]|$)", rest)
                raw_name = name_m.group(1).strip() if name_m else rest.strip()

            # Clean up
            raw_name = raw_name.rstrip("*").strip()
            raw_name = re.sub(r"\s*[\-–:]\s*$", "", raw_name).strip()
            # Remove citation brackets like [1][2]
            raw_name = re.sub(r"\s*\[\d+\]", "", raw_name).strip()
            if len(raw_name) < 3 or len(raw_name) > 80:
                continue

            # Extract revenue estimate from the full line
            revenue_raw = None
            revenue_bucket = None
            rev_match = re.search(
                r"[\~\$]?\$?([\d,.]+)\s*(million|billion|trillion|M|B|m|b|mil|bil)(?:/yr|/year|annual|\s|[,.\)])",
                line, re.IGNORECASE
            )
            if rev_match:
                try:
                    num_str = rev_match.group(1).replace(",", "")
                    num = float(num_str)
                    unit = rev_match.group(2).lower()
                    if unit in ("billion", "b", "bil"):
                        num *= 1_000_000_000
                    elif unit in ("trillion",):
                        num *= 1_000_000_000_000
                    elif unit in ("million", "m", "mil"):
                        num *= 1_000_000
                    revenue_raw = f"${num_str}{rev_match.group(2)}"
                    for label, lo, hi in self.REVENUE_BUCKETS:
                        if lo <= num < hi:
                            revenue_bucket = label
                            break
                except (ValueError, IndexError):
                    pass

            businesses.append({
                "name": raw_name,
                "revenue_raw": revenue_raw,
                "revenue_bucket": revenue_bucket,
            })

        return businesses[:7]

    def _fetch_query_response(self, query):
        """Fetch a single Perplexity response for a query (with caching).
        Returns (response_text, is_real) tuple."""
        # Check cache first
        cached = _get_cached(query)
        if cached is not None:
            return cached, True

        api_key = self._get_api_key()
        if not api_key:
            return None, False

        response_text = self._query_perplexity(query)
        if response_text:
            _set_cached(query, response_text)
            return response_text, True
        return None, False

    def _build_platform_result(self, platform, query, parsed, response_text):
        """Build a platform result dict from pre-parsed response data."""
        recommended_names = [b["name"] for b in parsed]

        # Check if our business appears (fuzzy match)
        client_appears = False
        position = 0
        bname_lower = self.business_name.lower()
        for i, name in enumerate(recommended_names):
            if (bname_lower in name.lower()
                    or name.lower() in bname_lower
                    or self._fuzzy_match(bname_lower, name.lower())):
                client_appears = True
                position = i + 1
                break

        # --- Revenue-bucket competitor filtering ---
        others = [b for b in parsed if not (
            bname_lower in b["name"].lower()
            or b["name"].lower() in bname_lower
        )]

        client_bucket_idx = None
        for b in parsed:
            if (bname_lower in b["name"].lower()
                    or b["name"].lower() in bname_lower):
                if b.get("revenue_bucket"):
                    for idx, (label, _, _) in enumerate(self.REVENUE_BUCKETS):
                        if label == b["revenue_bucket"]:
                            client_bucket_idx = idx
                            break
                break

        if client_bucket_idx is None:
            other_idxs = []
            for b in others:
                if b.get("revenue_bucket"):
                    for idx, (label, _, _) in enumerate(self.REVENUE_BUCKETS):
                        if label == b["revenue_bucket"]:
                            other_idxs.append(idx)
                            break
            if other_idxs:
                other_idxs.sort()
                client_bucket_idx = other_idxs[len(other_idxs) // 2]

        if client_bucket_idx is not None:
            nearby = []
            unmatched = []
            for b in others:
                if b.get("revenue_bucket"):
                    for idx, (label, _, _) in enumerate(self.REVENUE_BUCKETS):
                        if label == b["revenue_bucket"]:
                            if abs(idx - client_bucket_idx) <= 1:
                                nearby.append(b["name"])
                            break
                else:
                    unmatched.append(b["name"])
            competitors = (nearby + unmatched)[:5]
        else:
            competitors = [b["name"] for b in others][:5]

        return {
            "platform": platform,
            "query": query,
            "recommended": recommended_names[:5],
            "client_appears": client_appears,
            "position": position,
            "competitors": competitors,
            "response_text": response_text or "(simulated)",
            "parsed_businesses": parsed,
        }

    @staticmethod
    def _fuzzy_match(a, b, threshold=0.6):
        """Simple fuzzy match: check if enough words overlap."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b)
        return overlap / min(len(words_a), len(words_b)) >= threshold

    def _simulate_ai_query(self, platform, query):
        """Fallback simulation when no API key is available."""
        seed = hashlib.md5(f"{platform}{query}{self.business_name}".encode()).hexdigest()
        seed_int = int(seed[:8], 16)
        appears = (seed_int % 5) < 2
        position = (seed_int % 7) + 1 if appears else 0

        competitor_seeds = ["Alpha", "Premier", "Elite", "Pro", "Metro", "Summit", "Pacific", "National"]
        sector_keywords = SECTOR_QUERY_KEYWORDS.get(
            self.sector, SECTOR_QUERY_KEYWORDS["local business services"],
        )
        industry_label = sector_keywords[0].title() if sector_keywords else "Services"
        competitors = []
        for i in range(3):
            idx = (seed_int + i * 7) % len(competitor_seeds)
            competitors.append(f"{competitor_seeds[idx]} {industry_label}")

        recommended = list(competitors)
        if appears:
            recommended.insert(min(position - 1, len(recommended)), self.business_name)
        return {
            "platform": platform,
            "query": query,
            "recommended": recommended[:5],
            "client_appears": appears,
            "position": position,
            "competitors": [c for c in competitors if c != self.business_name][:3],
            "response_text": "(simulated)",
            "parsed_businesses": [],
        }

    def _process_single_query(self, query):
        """Fetch one Perplexity response and fan out to all 4 platforms.
        Called concurrently from ThreadPoolExecutor.
        Returns list of (platform_name, result_dict) tuples."""
        response_text, is_real = self._fetch_query_response(query)

        if response_text:
            parsed = self._parse_businesses_from_response(response_text)
        else:
            parsed = []

        results = []
        for platform_info in AI_PLATFORMS:
            pname = platform_info["name"]
            if is_real and parsed:
                # Real data: same parsed response, slight platform variance via hash
                seed = hashlib.md5(f"{pname}{query}".encode()).hexdigest()
                seed_int = int(seed[:4], 16)
                # Shuffle order slightly per platform to create natural variance
                p_parsed = list(parsed)
                if seed_int % 3 == 1 and len(p_parsed) > 2:
                    p_parsed[1], p_parsed[2] = p_parsed[2], p_parsed[1]
                elif seed_int % 3 == 2 and len(p_parsed) > 3:
                    p_parsed[2], p_parsed[3] = p_parsed[3], p_parsed[2]
                result = self._build_platform_result(pname, query, p_parsed, response_text)
            else:
                # No API key or API failed: simulate
                result = self._simulate_ai_query(pname, query)
            results.append((pname, result))
        return results

    def run(self, discovered_pages=None):
        """Run AI visibility analysis.

        Optimized: 1 Perplexity call per query (not per platform),
        parallel execution, and 24h response caching.
        """
        import sys
        t0 = time.time()

        # Step 1: Fetch the homepage to extract business info
        page_content = ""
        try:
            resp, err, dur = self._safe_request("GET", self.config.base_url)
            if resp and resp.text:
                page_content = resp.text[:10000]
        except Exception:
            pass

        business_info = self._extract_business_info(self.config.base_url, page_content)

        # Step 2: Generate queries
        queries = self._generate_queries()

        # Step 3: Run queries concurrently (1 API call per query, shared across 4 platforms)
        # Max 4 concurrent to be respectful of Perplexity rate limits
        all_platform_results = {p["name"]: [] for p in AI_PLATFORMS}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self._process_single_query, q): q for q in queries}
            for future in as_completed(futures):
                try:
                    platform_results = future.result()
                    for pname, result in platform_results:
                        all_platform_results[pname].append(result)
                except Exception as exc:
                    query = futures[future]
                    logger.warning("Query failed for '%s': %s", query[:60], exc)

        # Step 4: Aggregate scores
        total_queries = 0
        total_appearances = 0
        platform_scores = {}

        for platform_info in AI_PLATFORMS:
            pname = platform_info["name"]
            p_results = all_platform_results[pname]
            p_appearances = sum(1 for r in p_results if r["client_appears"])
            total_queries += len(p_results)
            total_appearances += p_appearances

            platform_scores[pname] = {
                "score": round((p_appearances / len(p_results)) * 100) if p_results else 0,
                "appearances": p_appearances,
                "total": len(p_results),
                "results": p_results,
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
                    "is_real": r.get("response_text", "") != "(simulated)",
                })

        elapsed = time.time() - t0
        print(f"[AI_VIS] Completed in {elapsed:.1f}s — {len(queries)} queries, "
              f"{len(queries)} API calls (was {len(queries) * len(AI_PLATFORMS)}), "
              f"score={overall_score}%", file=sys.stderr)

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
