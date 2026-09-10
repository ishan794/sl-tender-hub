# Scraper registry - add new scraper classes here as you add sites
from .mahaweli import MahaweliScraper
from .slpost import SLPostScraper
from .treasury import TreasuryScraper
# Login-protected site base class (edit credentials.py to point it at your site)
from .auth_base import AuthenticatedScraper, LoginError

# NOTE: MyTenderSiteScraper is deliberately not imported here, so that
# `python -m scrapers.my_tender_site` runs cleanly (no runpy warning).
# run_scraper.py imports it directly from scrapers.my_tender_site.

# Uncomment as you add more scrapers:
# from .promise import PromiseScraper
# from .npc import NPCScraper
# from .tenders_lk import TendersLKScraper
# from .srilankatender import SriLankaTenderScraper

ALL_SCRAPERS = [
    MahaweliScraper,
    SLPostScraper,
    TreasuryScraper,
    # PromiseScraper,
    # NPCScraper,
    # TendersLKScraper,
    # SriLankaTenderScraper,
]
