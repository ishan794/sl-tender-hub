"""
Template scraper for YOUR login-protected tender website.

Normally you do not need to touch this file at all:
    1. copy .env.example -> .env
    2. put the site link, login e-mail and password in it
    3. run:  python check_login.py      (test the login)
    4. run:  python run_scraper.py      (collect the data into tenders.db)

The scraper auto-detects the login form, the tender rows, the dates and the
document links. If your site uses unusual HTML you can pin the selectors here
(or in .env) - see the commented lines at the bottom.
"""
from typing import Dict, List

from credentials import MY_SITE, SiteCredentials
from .auth_base import AuthenticatedScraper


class MyTenderSiteScraper(AuthenticatedScraper):
    """Scraper for the private tender portal configured in credentials.py."""

    requires_credentials = True

    def __init__(self, creds: SiteCredentials = None):
        super().__init__(creds or MY_SITE)

    @classmethod
    def default_credentials(cls) -> SiteCredentials:
        return MY_SITE

    def scrape(self) -> List[Dict]:
        tenders = super().scrape()
        # Put anything site-specific here, e.g. skip a category you do not want:
        # tenders = [t for t in tenders if t["category"] != "other"]
        return tenders


if __name__ == "__main__":
    # `python -m scrapers.my_tender_site` -> scrape this site only and save it
    from database import init_db, insert_tender

    print("=" * 70)
    print("🔐 Logging in to:", MY_SITE.site_url)
    print(MY_SITE.safe_summary())
    print("=" * 70)

    scraper = MyTenderSiteScraper()
    results = scraper.scrape()

    init_db()
    saved = 0
    for tender in results:
        if insert_tender(tender, is_primary=1):
            saved += 1

    print("-" * 70)
    print(f"📊 Found {len(results)} tenders, 🆕 {saved} new rows saved to tenders.db")
