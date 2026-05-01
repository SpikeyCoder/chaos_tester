from __future__ import annotations

"""
Business Identifier Module
Extracts the correct business name, headquarters city, and business sector
from a website by scraping page content, scoring candidate names, and
performing reverse lookups against multiple business-record sources.
"""

import logging
import re
import json
import time
import threading
import requests
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# URL-keyed cache so the pre-flight /api/detect-business result is reused by
# the audit run, avoiding a second full identification pipeline.
_identify_cache: dict = {}
_identify_cache_lock = threading.Lock()
_IDENTIFY_CACHE_TTL = 900  # 15 minutes

# Legal entity suffixes, ordered longest-first so regex is greedy
ENTITY_SUFFIXES = [
    "Corporation", "Incorporated", "Limited Liability Company",
    "Limited Liability Partnership", "Limited Partnership",
    "Professional Limited Liability Company",
    "Corp", "Inc", "LLC", "LLP", "LP", "Ltd", "PLLC", "P.L.L.C.",
    "L.L.C.", "L.L.P.", "L.P.",
]
_SUFFIX_PATTERN = r"(?:" + "|".join(re.escape(s) for s in ENTITY_SUFFIXES) + r")\.?"
ENTITY_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&'\-\.\, ]{1,60})\s+" + _SUFFIX_PATTERN, re.MULTILINE
)

# Patterns that capture text near legal / copyright markers
COPYRIGHT_RE = re.compile(
    r"(?:©|\bcopyright\b|\(c\))\s*(?:\d{4}[\-–]\d{4}|\d{4})?\s*(.{3,80}?)(?:\.|All Rights|$)",
    re.IGNORECASE,
)

# Common person-name patterns (first + last)
PERSON_NAME_RE = re.compile(
    r"^[A-Z][a-z]+\s+(?:[A-Z]\.?\s+)?[A-Z][a-z]+$"
)

# IRS Exempt Organizations data (free, public)
IRS_EO_SEARCH_URL = "https://apps.irs.gov/app/eos/allSearch"
# OpenCorporates API (may require API key now)
OPENCORP_SEARCH_URL = "https://api.opencorporates.com/v0.4/companies/search"

# ── NTEE code → sector label ───────────────────────────────────────
NTEE_SECTOR_MAP = {
    "A": "arts and culture",
    "B": "education",
    "C": "environmental services",
    "D": "animal welfare",
    "E": "healthcare",
    "F": "mental health services",
    "G": "disease research",
    "H": "medical research",
    "I": "legal services",
    "J": "employment services",
    "K": "food and agriculture",
    "L": "housing services",
    "M": "public safety",
    "N": "recreation and sports",
    "O": "youth development",
    "P": "human services",
    "Q": "international affairs",
    "R": "civil rights services",
    "S": "community development",
    "T": "philanthropy",
    "U": "science and technology",
    "V": "social science research",
    "W": "public policy",
    "X": "religious services",
    "Y": "mutual benefit services",
    "Z": "general services",
}

# ── Business-name keywords → sector label ──────────────────────────
NAME_SECTOR_KEYWORDS = {
    "holdco":       "holding company services",
    "holding":      "holding company services",
    "holdings":     "holding company services",
    "capital":      "financial services",
    "ventures":     "venture capital",
    "invest":       "investment services",
    "realty":       "real estate",
    "properties":   "real estate",
    "property":     "real estate",
    "construction": "construction",
    "builders":     "construction",
    "tech":         "technology",
    "software":     "technology",
    "digital":      "digital services",
    "media":        "media and advertising",
    "health":       "healthcare",
    "medical":      "healthcare",
    "dental":       "dental services",
    "law":          "legal services",
    "legal":        "legal services",
    "consult":      "consulting",
    "advisory":     "consulting",
    "restaurant":   "restaurant",
    "food":         "food services",
    "auto":         "automotive services",
    "motor":        "automotive services",
    "electric":     "electrical services",
    "plumb":        "plumbing",
    "roof":         "roofing",
    "clean":        "cleaning services",
    "landscape":    "landscaping",
    "insur":        "insurance",
    "account":      "accounting",
    "market":       "marketing",
    "design":       "design services",
    "photo":        "photography",
    "salon":        "beauty and wellness",
    "spa":          "beauty and wellness",
    "fitness":      "fitness",
    "gym":          "fitness",
    "vet":          "veterinary services",
    "pet":          "pet services",
    "logistics":    "logistics and shipping",
    "transport":    "transportation",
    "energy":       "energy services",
    "solar":        "solar energy",
}

# ── Page-content keywords → sector label ───────────────────────────
PAGE_SECTOR_KEYWORDS = {
    "product management":   "technology and product development",
    "software development": "technology",
    "web development":      "technology",
    "ios development":      "mobile app development",
    "mobile app":           "mobile app development",
    "ecommerce":            "ecommerce and payments",
    "e-commerce":           "ecommerce and payments",
    "payment":              "ecommerce and payments",
    "artificial intelligence": "AI and technology",
    "machine learning":     "AI and technology",
    "real estate":          "real estate",
    "property management":  "real estate",
    "legal services":       "legal services",
    "law firm":             "legal services",
    "attorney":             "legal services",
    "healthcare":           "healthcare",
    "medical practice":     "healthcare",
    "dental":               "dental services",
    "orthodont":            "dental services",
    "roofing":              "roofing",
    "roof repair":          "roofing",
    "plumbing":             "plumbing",
    "hvac":                 "heating and cooling",
    "air conditioning":     "heating and cooling",
    "construction":         "construction",
    "general contractor":   "construction",
    "restaurant":           "restaurant",
    "catering":             "food services",
    "marketing agency":     "marketing and advertising",
    "digital marketing":    "marketing and advertising",
    "seo":                  "digital marketing",
    "consulting":           "consulting",
    "management consulting":"consulting",
    "financial planning":   "financial services",
    "investment":           "financial services",
    "wealth management":    "financial services",
    "insurance":            "insurance",
    "accounting":           "accounting and tax",
    "tax preparation":      "accounting and tax",
    "bookkeeping":          "accounting and tax",
    "photography":          "photography",
    "videography":          "media production",
    "fitness":              "fitness and wellness",
    "personal training":    "fitness and wellness",
    "salon":                "beauty and personal care",
    "landscaping":          "landscaping",
    "lawn care":            "landscaping",
    "pest control":         "pest control",
    "exterminator":         "pest control",
    "cleaning service":     "cleaning services",
    "janitorial":           "cleaning services",
    "auto repair":          "automotive services",
    "mechanic":             "automotive services",
    "veterinary":           "veterinary services",
    "animal hospital":      "veterinary services",
    "education":            "education",
    "tutoring":             "education",
    "child care":           "child care",
    "daycare":              "child care",
}

# Secondary pages that commonly contain addresses (trimmed for speed)
_SECONDARY_PATHS = ["/contact", "/about", "/contact-us"]

# US state abbreviations for validation
_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC",
}


class BusinessIdentifier:
    """Identifies the business name, headquarters city, and sector for a given website."""

    def __init__(self, session: requests.Session = None, timeout: int = 4):
        self.session = session or requests.Session()
        self.timeout = timeout
        self._irs_cache: dict = {}  # name -> IRS response, avoids duplicate calls

    # ------------------------------------------------------------------
    # Step 1 & 2: Scrape website and extract candidate names
    # ------------------------------------------------------------------
    def scrape_candidates(self, url: str, html: str = "") -> list[dict]:
        """
        Scrape the target website and return a list of candidate dicts:
          { "name": str, "score": float, "sources": list[str] }
        """
        if not html:
            try:
                resp = self.session.get(url, timeout=self.timeout, verify=True)
                html = resp.text
            except Exception as exc:
                logger.warning("BusinessIdentifier: could not fetch %s: %s", url, exc)
                return []

        soup = BeautifulSoup(html, "html.parser")

        # Remove script/style noise
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        candidates: Counter = Counter()   # name -> cumulative score
        sources: dict[str, list[str]] = {}  # name -> list of source labels

        def _add(name: str, source: str, weight: float):
            name = self._normalise(name)
            if not name or len(name) < 3:
                return
            candidates[name] += weight
            sources.setdefault(name, []).append(source)

        # --- Header region -------------------------------------------
        header = soup.find("header") or soup.find(attrs={"role": "banner"})
        if header:
            self._extract_from_region(header, "header", _add, weight=3.0)

        # --- Footer region -------------------------------------------
        footer = soup.find("footer") or soup.find(attrs={"role": "contentinfo"})
        if footer:
            self._extract_from_region(footer, "footer", _add, weight=3.0)

        # --- <title> tag ---------------------------------------------
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            parts = re.split(r"[|–—\-:]", title_tag.string)
            for part in parts:
                part = part.strip()
                if part:
                    _add(part, "title_tag", 2.0)

        # --- Meta tags (og:site_name, application-name) --------------
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "") or meta.get("name", "")
            content = meta.get("content", "")
            if prop in ("og:site_name", "application-name") and content:
                _add(content, "meta_tag", 2.5)

        # --- Copyright / legal text ----------------------------------
        full_text = soup.get_text(separator="\n")
        for m in COPYRIGHT_RE.finditer(full_text):
            _add(m.group(1), "copyright", 4.0)

        # --- Entity-suffix matches (LLC, Inc, …) across full text ----
        for m in ENTITY_RE.finditer(full_text):
            raw = m.group(0).strip().rstrip(".,")
            _add(raw, "entity_suffix", 5.0)

        # --- Structured data (JSON-LD) --------------------------------
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "")
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    org_name = item.get("name") or item.get("legalName", "")
                    if org_name:
                        _add(org_name, "json_ld", 4.0)
                    # Nested organization
                    org = item.get("organization") or item.get("publisher") or {}
                    if isinstance(org, dict) and org.get("name"):
                        _add(org["name"], "json_ld_nested", 3.5)
            except Exception:
                pass

        # Build output list sorted by descending score
        results = []
        for name, score in candidates.most_common():
            classification = self._classify(name)
            # Apply classification penalties
            if classification == "person":
                score *= 0.3
            elif classification == "phrase":
                score *= 0.5
            results.append({
                "name": name,
                "score": round(score, 2),
                "sources": sources.get(name, []),
                "classification": classification,
            })

        results.sort(key=lambda c: c["score"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Step 3: Score / classify a candidate name
    # ------------------------------------------------------------------
    def _classify(self, name: str) -> str:
        """Return 'business', 'person', or 'phrase'."""
        for suffix in ENTITY_SUFFIXES:
            if suffix.lower() in name.lower():
                return "business"
        if PERSON_NAME_RE.match(name):
            return "person"
        words = name.split()
        if len(words) > 6:
            return "phrase"
        return "business"

    # ------------------------------------------------------------------
    # Step 4: Pick the best business name
    # ------------------------------------------------------------------
    def pick_best(self, candidates: list[dict]) -> str:
        """Return the highest-confidence business name, or empty string."""
        for c in candidates:
            if c["classification"] == "business" and c["score"] >= 2.0:
                return c["name"]
        return candidates[0]["name"] if candidates else ""

    # ------------------------------------------------------------------
    # Step 5: Multi-source headquarters city lookup
    # ------------------------------------------------------------------
    def lookup_headquarters(self, business_name: str, url: str = "", html: str = "") -> tuple:
        """
        Look up the headquarters city using multiple sources in priority order.
        Returns (city_string, source_label) or ("", "").
        """
        # Source 1: JSON-LD / Schema.org structured data on the page
        if html:
            loc = self._extract_location_from_structured_data(html)
            if loc:
                logger.info("Location from structured data: %r", loc)
                return loc, "structured_data"

        # Source 2: Address / location patterns in page HTML
        if html:
            loc = self._extract_location_from_html(html)
            if loc:
                logger.info("Location from HTML patterns: %r", loc)
                return loc, "page_content"

        # Sources 3-4: IRS + secondary pages in parallel (skip OpenCorporates
        # which often returns 401, and WHOIS/RDAP which is slow with low hit rate).
        tasks = [
            ("irs_eo", self._lookup_irs_eo_location, business_name),
        ]
        if url:
            tasks.append(("secondary_page", self._scrape_secondary_pages, url))

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {label: executor.submit(fn, arg) for label, fn, arg in tasks}

        for label, _, _ in tasks:
            try:
                loc = futures[label].result()
                if loc:
                    logger.info("Location from %s: %r", label, loc)
                    return loc, label
            except Exception as exc:
                logger.debug("%s lookup failed: %s", label, exc)

        return "", ""

    # ------------------------------------------------------------------
    # Step 6: Sector / business purpose detection
    # ------------------------------------------------------------------
    def detect_sector(self, business_name: str, html: str = "") -> str:
        """
        Detect the business sector/purpose from multiple signals.
        Local signals first (instant), then IRS API only if needed.
        Returns a human-readable sector phrase for use in search queries.
        """
        # Signal 1 (instant): Business name keyword analysis
        name_lower = business_name.lower()
        for keyword, sector in NAME_SECTOR_KEYWORDS.items():
            if keyword in name_lower:
                logger.info("Sector from business name keyword %r: %r", keyword, sector)
                return sector

        # Signal 2 (instant): JSON-LD @type on the page
        if html:
            sector = self._detect_sector_from_jsonld(html)
            if sector:
                logger.info("Sector from JSON-LD @type: %r", sector)
                return sector

        # Signal 3 (instant): Page content keyword frequency analysis
        if html:
            sector = self._detect_sector_from_content(html)
            if sector:
                logger.info("Sector from page content: %r", sector)
                return sector

        # Signal 4 (network, uses cache): IRS NTEE code (for tax-exempt orgs)
        ntee = self._lookup_irs_eo_ntee(business_name)
        if ntee:
            sector_letter = ntee[0].upper()
            sector = NTEE_SECTOR_MAP.get(sector_letter, "")
            if sector:
                logger.info("Sector from IRS NTEE (%s): %r", ntee, sector)
                return sector

        return "local business services"

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def identify(self, url: str, html: str = "") -> dict:
        """
        Full pipeline: scrape → score → pick → lookup city → detect sector.
        Returns {
          "business_name": str,
          "location": str,
          "sector": str,
          "candidates": list[dict],
          "lookup_source": str,
        }
        Results are cached by URL for _IDENTIFY_CACHE_TTL seconds so that
        a pre-flight /api/detect-business call is reused by the audit run.
        """
        with _identify_cache_lock:
            entry = _identify_cache.get(url)
            if entry and time.time() - entry["ts"] < _IDENTIFY_CACHE_TTL:
                logger.info("BusinessIdentifier cache hit for %r", url)
                return entry["result"]

        candidates = self.scrape_candidates(url, html)
        business_name = self.pick_best(candidates)
        location = ""
        lookup_source = ""
        sector = "local business services"

        if business_name:
            with ThreadPoolExecutor(max_workers=2) as executor:
                hq_future = executor.submit(
                    self.lookup_headquarters, business_name, url, html
                )
                sector_future = executor.submit(self.detect_sector, business_name, html)
            try:
                location, lookup_source = hq_future.result()
            except Exception as exc:
                logger.warning("lookup_headquarters failed: %s", exc)
            try:
                sector = sector_future.result()
            except Exception as exc:
                logger.warning("detect_sector failed: %s", exc)

        # Fallback: try to extract location from the page itself
        # (already tried in lookup_headquarters, but just in case)
        if not location and html:
            location = self._extract_location_from_html(html)
            if location:
                lookup_source = "page_content"

        logger.info(
            "BusinessIdentifier result: name=%r location=%r sector=%r source=%r "
            "(top candidates: %s)",
            business_name, location, sector, lookup_source,
            [c["name"] for c in candidates[:5]],
        )

        result = {
            "business_name": business_name,
            "location": location,
            "sector": sector,
            "candidates": candidates[:10],
            "lookup_source": lookup_source,
        }

        with _identify_cache_lock:
            _identify_cache[url] = {"ts": time.time(), "result": result}

        return result

    # ==================================================================
    # Location extraction helpers
    # ==================================================================

    def _extract_location_from_structured_data(self, html: str) -> str:
        """Extract location from JSON-LD / Schema.org structured data."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(script.string or "")
                    items = ld if isinstance(ld, list) else [ld]
                    for item in items:
                        # Direct address on the org/business
                        loc = self._parse_schema_address(item.get("address"))
                        if loc:
                            return loc
                        # Nested location
                        loc_obj = item.get("location")
                        if isinstance(loc_obj, dict):
                            loc = self._parse_schema_address(loc_obj.get("address"))
                            if loc:
                                return loc
                            # location might itself have name (city)
                            loc_name = loc_obj.get("name", "")
                            if loc_name and len(loc_name) < 60:
                                return loc_name
                        # areaServed
                        area = item.get("areaServed")
                        if isinstance(area, dict):
                            area_name = area.get("name", "")
                            if area_name:
                                return area_name
                        elif isinstance(area, str) and area:
                            return area
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("Structured data extraction failed: %s", exc)
        return ""

    def _parse_schema_address(self, addr) -> str:
        """Parse a Schema.org PostalAddress object into 'City, ST'."""
        if not addr or not isinstance(addr, dict):
            return ""
        city = addr.get("addressLocality", "")
        region = addr.get("addressRegion", "")
        if city and region:
            return f"{city}, {region}"
        if city:
            return city
        if region:
            return region
        # Sometimes the address is just a text string
        text = addr.get("streetAddress", "") or addr.get("name", "")
        if text:
            # Try to extract city, state from the text
            m = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})", text)
            if m and m.group(2) in _US_STATES:
                return f"{m.group(1)}, {m.group(2)}"
        return ""

    def _extract_location_from_html(self, html: str) -> str:
        """Extract a location from page text using regex patterns."""
        # Pattern 1: Explicit location phrases
        location_patterns = [
            r"(?:located in|serving|based in|proudly serving|headquartered in|"
            r"headquarters?\s+in|offices?\s+in|main\s+office\s+in)\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, html)
            if match:
                loc = match.group(1).strip()
                # Validate state abbreviation if present
                parts = loc.split(",")
                if len(parts) == 2:
                    state = parts[1].strip()
                    if state in _US_STATES:
                        return loc
                elif loc:
                    return loc

        # Pattern 2: Full address with ZIP (City, ST ZIP)
        m = re.search(
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z]{2})\s+\d{5}",
            html,
        )
        if m and m.group(2) in _US_STATES:
            return f"{m.group(1)}, {m.group(2)}"

        # Pattern 3: Street address → City, ST
        m = re.search(
            r"\d{1,5}\s+[A-Z][A-Za-z\s\.]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|"
            r"Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl)\.?"
            r"\s*,?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z]{2})",
            html,
        )
        if m and m.group(2) in _US_STATES:
            return f"{m.group(1)}, {m.group(2)}"

        return ""

    def _scrape_one_secondary_page(self, page_url: str) -> str:
        """Fetch a single secondary page and extract a location string, or ""."""
        try:
            resp = self.session.get(
                page_url, timeout=min(self.timeout, 3), verify=True, allow_redirects=True,
            )
            if resp.status_code != 200:
                return ""
            page_html = resp.text[:15000]
            loc = self._extract_location_from_structured_data(page_html)
            if loc:
                return loc
            return self._extract_location_from_html(page_html)
        except Exception as exc:
            logger.debug("Secondary page %s failed: %s", page_url, exc)
            return ""

    def _scrape_secondary_pages(self, url: str) -> str:
        """Fetch /about, /contact, etc. in parallel and return first location found."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        page_urls = [urljoin(base, path) for path in _SECONDARY_PATHS]

        with ThreadPoolExecutor(max_workers=len(page_urls)) as executor:
            # Submit in path-priority order; iterate futures in the same order.
            futures = [executor.submit(self._scrape_one_secondary_page, u) for u in page_urls]
            for fut in futures:
                try:
                    loc = fut.result()
                    if loc:
                        return loc
                except Exception as exc:
                    logger.debug("Secondary page future failed: %s", exc)

        return ""

    def _infer_location_from_whois(self, url: str) -> str:
        """Try to get registrant location from WHOIS lookup via RDAP."""
        try:
            parsed = urlparse(url)
            domain = parsed.hostname or ""
            domain = re.sub(r"^www\.", "", domain)
            # Use RDAP (Registration Data Access Protocol) — public, machine-readable
            rdap_url = f"https://rdap.org/domain/{domain}"
            resp = self.session.get(rdap_url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                # Look in entities for registrant vCard
                for entity in data.get("entities", []):
                    roles = entity.get("roles", [])
                    if "registrant" in roles:
                        vcard = entity.get("vcardArray", [])
                        if len(vcard) >= 2:
                            for field in vcard[1]:
                                if field[0] == "adr" and len(field) >= 4:
                                    addr = field[3] if isinstance(field[3], dict) else {}
                                    city = addr.get("locality", "")
                                    region = addr.get("region", "")
                                    if city and region:
                                        return f"{city}, {region}"
        except Exception as exc:
            logger.debug("RDAP/WHOIS lookup failed: %s", exc)
        return ""

    # ==================================================================
    # API lookups
    # ==================================================================

    def _lookup_opencorporates(self, name: str) -> str:
        """Search OpenCorporates for the company and return registered city."""
        # Try multiple API URL patterns (v0.4 may require auth now)
        urls_to_try = [
            OPENCORP_SEARCH_URL,
            "https://api.opencorporates.com/companies/search",
        ]
        for api_url in urls_to_try:
            try:
                resp = self.session.get(
                    api_url,
                    params={"q": name, "jurisdiction_code": "us_*", "per_page": 1},
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    companies = data.get("results", {}).get("companies", [])
                    if companies:
                        co = companies[0].get("company", {})
                        addr = co.get("registered_address", {}) or {}
                        city = addr.get("locality", "")
                        region = addr.get("region", "")
                        if city and region:
                            return f"{city}, {region}"
                        if city:
                            return city
                        # Sometimes jurisdiction gives us the state
                        jurisdiction = co.get("jurisdiction_code", "")
                        if jurisdiction.startswith("us_"):
                            state = jurisdiction.replace("us_", "").upper()
                            if state in _US_STATES:
                                # We at least know the state
                                inc_date = co.get("incorporation_date", "")
                                company_name = co.get("name", "")
                                if company_name:
                                    return state  # Return state as fallback
                elif resp.status_code == 401:
                    logger.debug("OpenCorporates %s returned 401 (auth required)", api_url)
                    continue
                else:
                    logger.debug("OpenCorporates %s returned %d", api_url, resp.status_code)
            except Exception as exc:
                logger.debug("OpenCorporates lookup failed at %s for %r: %s", api_url, name, exc)
        return ""

    def _fetch_irs_eo(self, name: str) -> dict | None:
        """Fetch IRS EO data once, cache for reuse by location + NTEE lookups."""
        if name in self._irs_cache:
            return self._irs_cache[name]
        try:
            resp = self.session.get(
                IRS_EO_SEARCH_URL,
                params={
                    "names": name, "resultsPerPage": 1,
                    "orgTags": "", "type": "charities",
                },
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                orgs = data.get("organizations", [])
                result = orgs[0] if orgs else None
                self._irs_cache[name] = result
                return result
        except Exception as exc:
            logger.debug("IRS EO lookup failed for %r: %s", name, exc)
        self._irs_cache[name] = None
        return None

    def _lookup_irs_eo_location(self, name: str) -> str:
        """Extract city/state from cached IRS EO data."""
        org = self._fetch_irs_eo(name)
        if org:
            city = org.get("city", "")
            state = org.get("state", "")
            if city and state:
                return f"{city}, {state}"
        return ""

    def _lookup_irs_eo_ntee(self, name: str) -> str:
        """Extract NTEE code from cached IRS EO data."""
        org = self._fetch_irs_eo(name)
        if org:
            ntee = org.get("nteeCode", "") or org.get("nteeCd", "")
            if ntee:
                return ntee
        return ""

    # ==================================================================
    # Sector detection helpers
    # ==================================================================

    def _detect_sector_from_jsonld(self, html: str) -> str:
        """Extract sector from JSON-LD @type (Schema.org business types)."""
        schema_type_map = {
            "Restaurant": "restaurant",
            "Dentist": "dental services",
            "DentalClinic": "dental services",
            "LegalService": "legal services",
            "Attorney": "legal services",
            "RealEstateAgent": "real estate",
            "InsuranceAgency": "insurance",
            "FinancialService": "financial services",
            "AccountingService": "accounting",
            "AutoRepair": "automotive services",
            "AutoDealer": "automotive services",
            "HealthAndBeautyBusiness": "beauty and wellness",
            "HairSalon": "beauty and wellness",
            "DaySpa": "beauty and wellness",
            "MedicalBusiness": "healthcare",
            "Physician": "healthcare",
            "Hospital": "healthcare",
            "VeterinaryCare": "veterinary services",
            "SportsActivityLocation": "fitness and wellness",
            "ExerciseGym": "fitness and wellness",
            "EducationalOrganization": "education",
            "HomeAndConstructionBusiness": "construction",
            "Electrician": "electrical services",
            "Plumber": "plumbing",
            "RoofingContractor": "roofing",
            "LandscapingBusiness": "landscaping",
            "HVACBusiness": "heating and cooling",
            "ProfessionalService": "professional services",
            "LocalBusiness": "",  # too generic
            "Organization": "",
        }
        try:
            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(script.string or "")
                    items = ld if isinstance(ld, list) else [ld]
                    for item in items:
                        schema_type = item.get("@type", "")
                        if isinstance(schema_type, list):
                            schema_type = schema_type[0] if schema_type else ""
                        sector = schema_type_map.get(schema_type, "")
                        if sector:
                            return sector
                except Exception:
                    continue
        except Exception:
            pass
        return ""

    def _detect_sector_from_content(self, html: str) -> str:
        """Analyze page content keywords to determine business sector."""
        text_lower = html.lower() if isinstance(html, str) else ""
        sector_scores = Counter()

        for keyword, sector in PAGE_SECTOR_KEYWORDS.items():
            count = text_lower.count(keyword.lower())
            if count > 0:
                sector_scores[sector] += count

        if sector_scores:
            return sector_scores.most_common(1)[0][0]
        return ""

    # ==================================================================
    # General helpers
    # ==================================================================

    def _normalise(self, text: str) -> str:
        """Strip whitespace, collapse runs of spaces, drop stray punctuation."""
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        text = text.strip(".,;:!?\"'")
        if len(text) < 2 or len(text) > 80:
            return ""
        return text

    def _extract_from_region(self, tag, label, add_fn, weight=1.0):
        """Pull candidate names from a BeautifulSoup tag region."""
        region_text = tag.get_text(separator="\n")
        for m in ENTITY_RE.finditer(region_text):
            raw = m.group(0).strip().rstrip(".,")
            add_fn(raw, f"{label}_entity", weight + 3.0)
        for m in COPYRIGHT_RE.finditer(region_text):
            add_fn(m.group(1), f"{label}_copyright", weight + 2.0)
        for el in tag.find_all(["h1", "h2", "h3"]):
            text = el.get_text(strip=True)
            if text:
                add_fn(text, f"{label}_heading", weight)
        for el in tag.find_all("a"):
            cls = " ".join(el.get("class", []))
            if re.search(r"brand|logo|site.?name", cls, re.IGNORECASE):
                text = el.get_text(strip=True)
                if text:
                    add_fn(text, f"{label}_brand_link", weight + 1.0)
        for img in tag.find_all("img"):
            alt = img.get("alt", "")
            cls = " ".join(img.get("class", []))
            if re.search(r"logo|brand", cls + " " + alt, re.IGNORECASE) and alt:
                add_fn(alt, f"{label}_logo_alt", weight + 0.5)
