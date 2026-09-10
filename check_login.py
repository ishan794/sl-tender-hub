#!/usr/bin/env python3
"""
🔐 check_login.py — test the login for your tender site BEFORE scraping.

    python check_login.py                 # log in + show what was found
    python check_login.py --pages 3       # walk 3 list pages
    python check_login.py --no-details    # faster: list rows only
    python check_login.py --save          # save the pages to data/debug/

It never prints your password. It tells you exactly which pointer is still
missing if the login details are not filled in yet.
"""
import argparse
import sys
from pathlib import Path

import config
from credentials import MY_SITE
from scrapers.auth_base import AuthenticatedScraper, LoginError
from scrapers.my_tender_site import MyTenderSiteScraper


def save_snapshot(scraper: AuthenticatedScraper, name: str, content: str) -> Path:
    folder = Path(config.DEBUG_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{scraper.site_id}_{name}"
    path.write_text(content or "", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Test the login of your tender site")
    parser.add_argument("--pages", type=int, default=1, help="how many list pages to walk (default 1)")
    parser.add_argument("--no-details", action="store_true", help="do not open each notice page")
    parser.add_argument("--save", action="store_true", help="save the pages to data/debug/ for tuning")
    parser.add_argument("--limit", type=int, default=10, help="how many results to print (default 10)")
    args = parser.parse_args()

    print("=" * 72)
    print("🔐 Tender site login check")
    print("=" * 72)
    print(MY_SITE.safe_summary())
    print("-" * 72)

    if not MY_SITE.is_complete:
        print("❌ Not ready. These pointers are still empty:")
        for item in MY_SITE.missing:
            print(f"     - {item}")
        print("\nFix it with either:")
        print("   1) cp .env.example .env   then edit .env   (recommended)")
        print("   2) edit credentials.py directly (the 👉 POINTER lines)")
        return 1

    scraper = MyTenderSiteScraper()
    scraper.creds.fetch_details = not args.no_details
    scraper.creds.max_pages = args.pages

    try:
        scraper.login()
    except LoginError as exc:
        print(f"❌ Login FAILED: {exc}")
        print("\nChecklist:")
        print(f"   - open {scraper.login_url} in your browser and log in manually")
        print("   - is the e-mail / password correct?")
        print("   - if the login page link is different, set TENDER_LOGIN_URL in .env")
        print("   - if the site has an API login instead of a form, set TENDER_AUTH_METHOD=json")
        return 2

    print("✅ Login OK")

    if args.save:
        list_url = scraper._page_url(scraper.creds.start_page)
        response = scraper.get(list_url)
        if response is not None:
            print(f"💾 Saved list page ({response.status_code}) -> {save_snapshot(scraper, 'list.html', response.text)}")

    print("-" * 72)
    print(f"🔎 Reading tender list ({args.pages} page(s)) ...")
    try:
        tenders = scraper.scrape()
    except LoginError as exc:
        print(f"❌ Could not read the data: {exc}")
        return 3

    if not tenders:
        print("⚠️  Logged in, but no tender rows were found on the list page.")
        print("   -> set TENDER_LIST_URL (the page that lists the tenders) in .env")
        print("   -> or set TENDER_ROW_SELECTOR (CSS selector of one tender row) in .env")
        print("   -> run again with --save and open data/debug/ to see the page")
        return 4

    print(f"✅ Found {len(tenders)} tenders. First {min(args.limit, len(tenders))}:")
    for tender in tenders[: args.limit]:
        print(f"   • {tender['title'][:78]}")
        print(f"     closing={tender.get('closing_date')} | category={tender.get('category')} "
              f"| status={tender.get('status')} | docs={len(tender.get('document_links') or [])}")
        print(f"     {tender.get('source_url')}")

    print("-" * 72)
    print("Next step ->  python run_scraper.py   (saves everything to tenders.db)")
    print("      or  ->  python -m scrapers.my_tender_site   (this site only)")
    return 0


if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
