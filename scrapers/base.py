import time
import cloudscraper
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from config import USER_AGENT, REQUEST_TIMEOUT, MAX_RETRIES, SCRAPE_DELAY

class BaseScraper:
    """Base class for all site scrapers with shared logic (low memory usage)"""
    site_id: str = None
    site_name: str = None
    base_url: str = None

    def __init__(self):
        # Use cloudscraper for basic Cloudflare bypass, lighter than full browser automation
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        self.scraper.headers.update({"User-Agent": USER_AGENT})
        self.tenders_found = 0
        self.new_tenders = 0

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page, with automatic retries"""
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(SCRAPE_DELAY)  # Polite delay to avoid getting blocked
                response = self.scraper.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    print(f"Failed to fetch {url}: {str(e)}")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff for retries
        return None

    def parse_date(self, date_str: str) -> Optional[str]:
        """Parse Sri Lankan date formats to standard ISO format (YYYY-MM-DD).

        ISO dates (YYYY-MM-DD) are handled directly first — using dayfirst=True
        alone would corrupt them (e.g. 2026-12-01 -> 2026-01-12). Only ambiguous
        formats like DD/MM/YYYY fall through to the fuzzy dayfirst parser.
        """
        if not date_str:
            return None
        date_str = str(date_str).strip()
        import re
        from datetime import date
        # Unambiguous ISO prefix: YYYY-MM-DD (optionally followed by time)
        iso = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if iso:
            year, month, day = iso.groups()
            try:
                date(int(year), int(month), int(day))
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except ValueError:
                pass  # not a real calendar date, fall through
        try:
            from dateutil import parser
            parsed = parser.parse(date_str, fuzzy=True, dayfirst=True)
            return parsed.strftime("%Y-%m-%d")
        except Exception:
            return None

    def pick_date(self, item: Dict, keys: List[str]) -> Optional[str]:
        """Try multiple field names on an API record and return the first parsable date.

        API schemas differ between sites (published_date vs publishedDate vs
        created_at, etc.), which was the main cause of missing dates. This helper
        checks every candidate key so collected data actually matches the source.
        """
        for key in keys:
            value = item.get(key)
            if value:
                parsed = self.parse_date(str(value))
                if parsed:
                    return parsed
        return None

    def extract_date_from_text(self, text: str, patterns: List[str]) -> Optional[str]:
        """Search free text for a date using labeled regex patterns (e.g. closing date)."""
        if not text:
            return None
        import re
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parsed = self.parse_date(match.group(1))
                if parsed:
                    return parsed
        return None

    def scrape(self) -> List[Dict]:
        """Main scrape method - must be implemented for each site"""
        raise NotImplementedError("Each scraper must implement a scrape() method")
