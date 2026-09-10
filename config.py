import os
from pathlib import Path

# Project root
BASE_DIR = Path(__file__).parent.resolve()

# Database configuration: single SQLite file stored locally, no separate server needed
# All tender data will be saved to this file
DB_PATH = os.getenv("TENDER_DB_PATH", BASE_DIR / "tenders.db")

# Scraper settings
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 8  # seconds - reduced for faster runs
MAX_RETRIES = 1  # reduced
SCRAPE_DELAY = 1  # seconds between requests to avoid overwhelming sites (polite scraping)

# Standardized tender categories (matches across all sites)
CATEGORIES = [
    "construction", "goods", "services", "consultancy", "IT",
    "health", "education", "transport", "agriculture", "energy", "other"
]

# Site registry - add new sites here as you expand
SITES = [
    {"id": "promise", "name": "PROMISE e-Procurement", "url": "https://www.promise.lk", "type": "government"},
    {"id": "treasury", "name": "Ministry of Finance Treasury", "url": "https://www.treasury.gov.lk/web/procurement", "type": "government"},
    {"id": "npc", "name": "National Procurement Commission", "url": "https://nprocom.gov.lk", "type": "government"},
    {"id": "tenders_lk", "name": "Tenders.lk", "url": "https://www.tenders.lk", "type": "private_aggregator"},
    {"id": "srilankatender", "name": "SriLankaTender.com", "url": "https://www.srilankatender.com", "type": "private_aggregator"},
    {"id": "mahaweli", "name": "Mahaweli Authority", "url": "https://mahaweli.gov.lk", "type": "government_institution"},
    {"id": "slpost", "name": "Sri Lanka Post", "url": "https://slpost.gov.lk", "type": "government_institution"},
]
