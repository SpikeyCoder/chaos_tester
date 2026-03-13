"""
Business Identifier Module
Extracts the correct business name and headquarters city from a website
by scraping page content, scoring candidate names, and performing
a reverse lookup against IRS business records.
"""

import logging
import re
import requests
from collections import Counter
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

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

# IRS Exempt Organizations data (free, public CSV hosted by IRS)
IRS_EO_SEARCH_URL = "https://apps.irs.gov/app/eos/allSearch"
# Fallback: OpenCorporates API (free tier, no key needed for basic lookups)
OPENCORP_SEARCH_URL = "https://api.opencorporates.com/v0.4/companies/search"


class BusinessIdentifier:
    """Identifies the business name and headquarters city for a given website."""

    def __init__(self, session: requests.Session = None, timeout: int = 10):
        self.session = session or requests.Session()
        self.timeout = timeout

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
                import json
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
        # If it contains a legal entity suffix -> definitely business
        for suffix in ENTITY_SUFFIXES:
            if suffix.lower() in name.lower():
                return "business"
        # If it matches "Firstname Lastname" pattern -> likely person
        if PERSON_NAME_RE.match(name):
            return "person"
        # Heuristic: mostly lowercase words with common filler -> phrase
        words = name.split()
        if len(words) > 6:
            return "phrase"
        # Default to business for shorter proper-cased strings
        return "business"

    # ------------------------------------------------------------------
    # Step 4: Pick the best business name
    # ------------------------------------------------------------------
    def pick_best(self, candidates: list[dict]) -> str:
        """Return the highest-confidence business name, or empty string."""
        for c in candidates:
            if c["classification"] == "business" and c["score"] >= 2.0:
                return c["name"]
        # Fallback: first candidate regardless of type
        return candidates[0]["name"] if candidates else ""

    # ------------------------------------------------------------------
    # Step 5: Reverse-lookup headquarters city
    # ------------------------------------------------------------------
    def lookup_headquarters(self, business_name: str) -> str:
        """
        Look up the headquarters city for *business_name* via public
        business-record sources.  Returns 'City, ST' or empty string.
        """
        city = self._lookup_opencorporates(business_name)
        if city:
            return city
        city = self._lookup_irs_eo(business_name)
        if city:
            return city
        return ""

    def _lookup_opencorporates(self, name: str) -> str:
        """Search OpenCorporates for the company and return registered city."""
        try:
            resp = self.session.get(
                OPENCORP_SEARCH_URL,
                params={"q": name, "jurisdiction_code": "us_*", "per_page": 1},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                companies = (
                    data.get("results", {}).get("companies", [])
                )
                if companies:
                    co = companies[0].get("company", {})
                    addr = co.get("registered_address", {}) or {}
                    city = addr.get("locality", "")
                    region = addr.get("region", "")
                    if city and region:
                        return f"{city}, {region}"
                    if city:
                        return city
        except Exception as exc:
            logger.debug("OpenCorporates lookup failed for %r: %s", name, exc)
        return ""

    def _lookup_irs_eo(self, name: str) -> str:
        """Search IRS Exempt Organizations database for city/state."""
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
                if orgs:
                    city = orgs[0].get("city", "")
                    state = orgs[0].get("state", "")
                    if city and state:
                        return f"{city}, {state}"
        except Exception as exc:
            logger.debug("IRS EO lookup failed for %r: %s", name, exc)
        return ""

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def identify(self, url: str, html: str = "") -> dict:
        """
        Full pipeline: scrape ➜ score ➜ pick ➜ lookup.
        Returns {
          "business_name": str,
          "location": str,
          "candidates": list[dict],
          "lookup_source": str,
        }
        """
        candidates = self.scrape_candidates(url, html)
        business_name = self.pick_best(candidates)
        location = ""
        lookup_source = ""

        if business_name:
            location = self.lookup_headquarters(business_name)
            if location:
                lookup_source = "business_records"

        # Fallback: try to extract location from the page itself
        if not location and html:
            location = self._extract_location_from_html(html)
            if location:
                lookup_source = "page_content"

        logger.info(
            "BusinessIdentifier result: name=%r location=%r source=%r (top candidates: %s)",
            business_name, location, lookup_source,
            [c["name"] for c in candidates[:5]],
        )

        return {
            "business_name": business_name,
            "location": location,
            "candidates": candidates[:10],
            "lookup_source": lookup_source,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalise(self, text: str) -> str:
        """Strip whitespace, collapse runs of spaces, drop stray punctuation."""
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        text = text.strip(".,;:!?\"'")
        # Drop very short or very long junk
        if len(text) < 2 or len(text) > 80:
            return ""
        return text

    def _extract_from_region(self, tag, label, add_fn, weight=1.0):
        """Pull candidate names from a BeautifulSoup tag region."""
        # Check for entity suffix matches first (highest value)
        region_text = tag.get_text(separator="\n")
        for m in ENTITY_RE.finditer(region_text):
            raw = m.group(0).strip().rstrip(".,")
            add_fn(raw, f"{label}_entity", weight + 3.0)
        for m in COPYRIGHT_RE.finditer(region_text):
            add_fn(m.group(1), f"{label}_copyright", weight + 2.0)
        # Check prominent text (h1-h3, a with class containing 'brand'/'logo')
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
        # img alt text for logos
        for img in tag.find_all("img"):
            alt = img.get("alt", "")
            cls = " ".join(img.get("class", []))
            if re.search(r"logo|brand", cls + " " + alt, re.IGNORECASE) and alt:
                add_fn(alt, f"{label}_logo_alt", weight + 0.5)

    def _extract_location_from_html(self, html: str) -> str:
        """Fallback: extract a location from page text using regex patterns."""
        location_patterns = [
            r"(?:located in|serving|based in|proudly serving|headquarters?\s+in)\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s+\d{5}",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, html)
            if match:
                if match.lastindex == 1:
                    return match.group(1)
                return f"{match.group(1)}, {match.group(2)}"
        return ""
