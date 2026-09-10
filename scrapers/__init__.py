# Scraper registry - add new scraper classes here as you add sites
from .mahaweli import MahaweliScraper
from .slpost import SLPostScraper
from .treasury import TreasuryScraper

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
