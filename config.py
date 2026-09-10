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

# ---------------------------------------------------------------------------
# Data collection policy
# The hub must collect and keep ALL data: old + new tenders.
# ---------------------------------------------------------------------------

# Collect the FULL history from every source (paginate until the source runs out
# of results). When True, closed/expired tenders are also collected and stored
# (they are marked with status='closed' instead of being skipped).
COLLECT_ALL_DATA = os.getenv("COLLECT_ALL_DATA", "1") not in ("0", "false", "False")

# Delete tenders that have been closed for more than N days.
# None or 0 = NEVER delete anything (default) — all historical data is kept.
# Set to an int (e.g. 20) only if you explicitly want old data purged.
DELETE_CLOSED_AFTER_DAYS = None

# Safety cap for pagination. None = keep going until the source returns no more
# results. Set to an int (e.g. 100) to limit how many pages each source is walked.
MAX_PAGES_PER_SITE = None

# Safety cap for how many tenders are processed from one source in one run.
# None = no cap (collect everything). Set to an int to bound a single run.
MAX_TENDERS_PER_SITE = None

# How many existing tenders to load into memory for cross-site duplicate
# detection. None = load all of them. Lower this only if RAM becomes a problem.
DEDUP_LOAD_LIMIT = None

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
