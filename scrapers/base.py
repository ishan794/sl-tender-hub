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
        """Parse Sri Lankan date formats to standard ISO format (YYYY-MM-DD)"""
        if not date_str:
            return None
        date_str = date_str.strip()
        try:
            from dateutil import parser
            parsed = parser.parse(date_str, fuzzy=True, dayfirst=True)
            return parsed.strftime("%Y-%m-%d")
        except:
            return None

    def scrape(self) -> List[Dict]:
        """Main scrape method - must be implemented for each site"""
        raise NotImplementedError("Each scraper must implement a scrape() method")
