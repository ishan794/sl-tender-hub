#!/usr/bin/env python3
"""
Main script to run all tender scrapers and save data to local database.
- Smart cross-site deduplication
- Priority-based scheduling (priority 1 sites run daily, others less frequently)
- Low memory usage: <300MB peak
"""
import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from datetime import datetime

import config
from database import init_db, insert_tender, log_scrape_run, mark_expired_tenders, delete_expired_tenders, get_all_existing_tenders, add_duplicate_source
from sources import get_sources_by_priority
from scrapers import ALL_SCRAPERS
from scrapers.generic import GenericScraper
from scrapers.treasury import TreasuryScraper
from scrapers.mahaweli import MahaweliScraper
from scrapers.slpost import SLPostScraper
from scrapers.tenders_lk import TendersLKScraper
from scrapers.tendernotices import TenderNoticesScraper
from scrapers.srilankatender import SriLankaTenderScraper
from scrapers.smarttenders import SmartTendersScraper
from scrapers.etenders import ETendersScraper
from deduplicator import find_matching_tender
import hashlib

def run_all_scrapers(priority: int = None):
    print("="*70)
    print(f"🇱🇰  Sri Lanka Tender Hub - Starting scraper run")
    print(f"⏰ Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Initialize database on first run
    init_db()
    print("✅ Local database ready")

    # Auto-close expired tenders (closing date passed) - only updates status, data is kept
    closed = mark_expired_tenders()
    if closed > 0:
        print(f"⏱️  Marked {closed} expired tenders as closed")

    # Keep ALL historical data by default. Old/closed tenders are only purged if
    # DELETE_CLOSED_AFTER_DAYS is explicitly set in config (or the env var).
    if config.DELETE_CLOSED_AFTER_DAYS:
        deleted = delete_expired_tenders(days_after_closing=config.DELETE_CLOSED_AFTER_DAYS)
        if deleted > 0:
            print(f"🗑️  Deleted {deleted} tenders closed for >{config.DELETE_CLOSED_AFTER_DAYS} days\n")
    else:
        print("💾 Keeping ALL historical tender data (old + new) — deletion is disabled\n")

    # Load existing tenders in memory for duplicate comparison (full history by default)
    existing_tenders = get_all_existing_tenders(limit=config.DEDUP_LOAD_LIMIT)
    print(f"📋 Loaded {len(existing_tenders)} existing tenders for duplicate detection\n")

    # Custom scrapers for sites with special structures
    custom_scrapers = {
        "treasury": TreasuryScraper,
        "mahaweli": MahaweliScraper,
        "slpost": SLPostScraper,
        "tenders_lk": TendersLKScraper,
        "tendernotices": TenderNoticesScraper,
        "srilankatender": SriLankaTenderScraper,
        "smarttenders": SmartTendersScraper,
        "etenders": ETendersScraper,
    }

    sources = get_sources_by_priority(priority)
    total_found = 0
    total_new = 0
    total_duplicates = 0
    failed_sites = []
    skipped_sites = []

    for source in sources:
        # Select appropriate scraper
        if source.id in custom_scrapers:
            scraper = custom_scrapers[source.id]()
        elif source.scraper_strategy == "custom" and source.id not in custom_scrapers:
            skipped_sites.append(source.name)
            log_scrape_run(source.id, "skipped", error_message="Custom scraper not yet implemented")
            continue
        elif source.scraper_strategy in ["generic_wp", "joomla", "discover", "nextjs"]:
            scraper = GenericScraper(
                source_id=source.id,
                name=source.name,
                base_url=source.base_url,
                tender_url=source.tender_url,
                strategy=source.scraper_strategy
            )
        else:
            # Default to generic scraper
            scraper = GenericScraper(
                source_id=source.id,
                name=source.name,
                base_url=source.base_url,
                tender_url=source.tender_url,
                strategy="generic_wp"
            )

        print(f"🔍 Scraping [{source.priority}] {source.name}...")
        try:
            tenders = scraper.scrape()
            new_count = 0
            dup_count = 0

            for tender in tenders:
                # Check if this tender is a duplicate (cross-site)
                duplicate_id = find_matching_tender(tender, existing_tenders)

                if duplicate_id:
                    # This is a cross-site duplicate, add to sources of existing tender
                    for existing in existing_tenders:
                        if existing['source_id'] == duplicate_id:
                            add_duplicate_source(
                                master_group_id=existing['master_group_id'],
                                source_site_id=tender['source_site_id'],
                                source_id=tender['source_id'],
                                source_url=tender['source_url']
                            )
                            # Also insert as alias record
                            insert_tender(
                                tender,
                                master_group_id=existing['master_group_id'],
                                is_primary=0,
                                duplicate_of=duplicate_id
                            )
                            dup_count +=1
                            break
                else:
                    # New unique tender
                    master_id = hashlib.md5(tender['source_url'].encode()).hexdigest()[:12]
                    if insert_tender(tender, master_group_id=master_id, is_primary=1):
                        new_count +=1
                        tender['master_group_id'] = master_id
                        tender['is_primary'] = 1
                        existing_tenders.append(tender)

            total_found += scraper.tenders_found
            total_new += new_count
            total_duplicates += dup_count

            log_scrape_run(
                site_id=source.id,
                status="success",
                tenders_found=scraper.tenders_found,
                new_tenders=new_count,
                duplicates=dup_count
            )
            status = f"✅ {source.name}: Found {scraper.tenders_found} notices, {new_count} new, {dup_count} cross-site duplicates"
            print(status)

        except Exception as e:
            error_msg = str(e)[:200]
            log_scrape_run(
                site_id=source.id,
                status="failed",
                error_message=error_msg
            )
            failed_sites.append(source.name)
            print(f"❌ {source.name}: Failed - {error_msg}")

    print("\n" + "="*70)
    print("🏁 Scrape run complete!")
    print(f"📊 Total notices found: {total_found}")
    print(f"🆕 New unique tenders saved: {total_new}")
    print(f"🔄 Cross-site duplicates detected: {total_duplicates}")
    print("="*70)

    # Automatically sync freshly scraped tenders to TenderHub web platform if local php spark is present
    try:
        import subprocess
        import os
        import shutil
        spark_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api", "spark"))
        php_bin = shutil.which("php") or (r"C:\php\php.exe" if os.path.exists(r"C:\php\php.exe") else None)
        if php_bin and os.path.exists(spark_path):
            print("\n🔄 Automatically syncing to TenderHub Web Platform...")
            res = subprocess.run([php_bin, spark_path, "hub:sync"], capture_output=True, text=True)
            print(res.stdout)
    except Exception as sync_err:
        pass


    return total_new


if __name__ == "__main__":
    priority = None
    if len(sys.argv) > 1:
        try:
            priority = int(sys.argv[1])
            print(f"⚙️  Running priority {priority} sources only")
        except ValueError:
            pass
    run_all_scrapers(priority)
