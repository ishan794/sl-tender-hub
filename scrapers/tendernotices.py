"""
TenderNotices.lk Scraper
Scrapes government and private tenders from TenderNotices.lk public listings
"""
from typing import List, Dict
import re
from datetime import datetime
from bs4 import BeautifulSoup
from .base import BaseScraper

class TenderNoticesScraper(BaseScraper):
    site_id = "tendernotices"
    site_name = "TenderNotices.lk"
    base_url = "https://www.tendernotices.lk"

    def __init__(self):
        super().__init__()
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.timeout = 30

    def fetch_page(self, url: str):
        """Fetch and parse page using dedicated requests session with retry"""
        import time
        from bs4 import BeautifulSoup
        for attempt in range(3):
            try:
                time.sleep(1)
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, 'html.parser')
            except Exception as e:
                if attempt == 2:
                    print(f"Failed to fetch {url}: {e}")
                    return None
                time.sleep(2 * (attempt + 1))
        return None

    def parse_sl_date(self, date_str: str):
        if not date_str:
            return None
        # e.g. "1st October 2026", "7th September 2026", "24/09/2026", "2026-10-01"
        clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str.strip())
        clean = re.sub(r'\s+', ' ', clean)
        formats = [
            '%d %B %Y',      # 1 October 2026
            '%d %b %Y',      # 1 Oct 2026
            '%d-%m-%Y',      # 01-10-2026
            '%d/%m/%Y',      # 01/10/2026
            '%Y-%m-%d',      # 2026-10-01
        ]
        for fmt in formats:
            try:
                return datetime.strptime(clean, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        # Fallback to base parse_date
        return self.parse_date(clean)

    def categorize(self, text: str) -> str:
        text = text.lower()
        if any(k in text for k in ['security', 'cleaning', 'janitorial', 'pest control', 'consult', 'service', 'maintenance', 'catering', 'insurance', 'rubbish', 'garbage', 'waste', 'repair']):
            return "services"
        elif any(k in text for k in ['hiring', 'rental', 'rent', 'transport', 'vehicle', 'bus', 'van', 'lorry', 'railway', 'logistics', 'freight', 'sedan', 'car']):
            return "transport"
        elif any(k in text for k in ['construction', 'civil', 'building', 'road', 'irrigation', 'renovation', 'rehabilitation', 'bridge', 'carpeting', 'asphalt']):
            return "construction"
        elif any(k in text for k in ['it ', 'software', 'hardware', 'system', 'network', 'website', 'computer', 'server', 'database', 'ups', 'cyber', 'surveillance', 'cctv']):
            return "it"
        elif any(k in text for k in ['medicine', 'medical', 'pharmaceutical', 'hospital', 'drug', 'surgical', 'laboratory', 'health']):
            return "goods"
        elif any(k in text for k in ['agriculture', 'seed', 'fertilizer', 'livestock', 'fisheries', 'crop', 'tea', 'rubber', 'coconut', 'animal']):
            return "agriculture"
        elif any(k in text for k in ['energy', 'electricity', 'power', 'solar', 'transformer', 'fuel', 'petroleum', 'gas', 'generator']):
            return "energy"
        elif any(k in text for k in ['education', 'university', 'school', 'training', 'research', 'books']):
            return "education"
        elif any(k in text for k in ['supply', 'goods', 'equipment', 'machine', 'printer', 'material', 'spare parts', 'stationery', 'furniture', 'purchase']):
            return "goods"
        return "other"

    def extract_organization(self, title: str, text: str) -> str:
        """Attempt to extract the issuing authority from the tender text or title"""
        combined = title + " " + text
        # Common organization patterns in Sri Lanka
        patterns = [
            r'((?:Ministry|Department)\s+of\s+[A-Za-z\s,&]+?)(?:\s*-\s*|\s*–\s*|\s*\(|\s*\n|$)',
            r'([A-Za-z\s,&]+?(?:Municipal Council|Urban Council|Pradeshiya Sabha))',
            r'([A-Za-z\s,&]+?(?:Authority|Board|Corporation|Commission|University|Hospital|Bank))',
        ]
        for pat in patterns:
            m = re.search(pat, combined, re.I)
            if m:
                org = m.group(1).strip()
                if 5 < len(org) < 80:
                    return org
        return "Government of Sri Lanka"

    def scrape(self, max_pages: int = 20) -> List[Dict]:
        tenders = []
        seen_urls = set()

        # Scrape through pages of tenders-sri-lanka
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/tenders-sri-lanka?page={page}"
            try:
                soup = self.fetch_page(url)
                if not soup:
                    break

                items = soup.find_all('div', class_='tender')
                if not items:
                    # If no items found on this page, stop paginating
                    break

                for it in items:
                    # Title
                    title_el = it.find('div', class_=re.compile(r'tender-t[i|l]lte|tender-title'))
                    if not title_el:
                        title_el = it.find('h3')
                    raw_title = title_el.get_text(' ', strip=True) if title_el else ''
                    clean_title = re.sub(r'\s+', ' ', raw_title).strip()
                    if not clean_title or len(clean_title) < 5:
                        continue

                    # Extract structured fields from .tender-detals paragraphs
                    raw_cat = ''
                    location = 'Western Province, Colombo'
                    closing_raw = ''
                    ref = ''

                    for p in it.select('.tender-detals p'):
                        p_text = p.get_text(' ', strip=True)
                        p_text = re.sub(r'\s+', ' ', p_text)
                        
                        if p_text.lower().startswith('category:'):
                            raw_cat = p_text.split(':', 1)[1].strip()
                        elif p_text.lower().startswith('location:'):
                            loc_val = p_text.split(':', 1)[1].strip()
                            if loc_val:
                                location = loc_val
                        elif p_text.lower().startswith('closing date:'):
                            closing_raw = p_text.split(':', 1)[1].strip()
                        elif p_text.lower().startswith('reference no:'):
                            ref = p_text.split(':', 1)[1].strip()

                    # Fallback ref from text if needed
                    if not ref:
                        ref_m = re.search(r'Reference\s*No:?\s*([A-Za-z0-9_-]+)', it.get_text(' ', strip=True), re.I)
                        if ref_m:
                            ref = ref_m.group(1).strip()

                    # Detail link
                    link_a = it.find('a', href=re.compile(r'/tender/[A-Za-z0-9_-]+', re.I))
                    if link_a and link_a.get('href'):
                        href = link_a['href']
                        detail_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    elif ref:
                        detail_url = f"{self.base_url}/tender/{ref}"
                    else:
                        import hashlib
                        detail_url = f"{self.base_url}/tender/{hashlib.md5(clean_title.encode()).hexdigest()[:10]}"

                    if detail_url in seen_urls:
                        continue
                    seen_urls.add(detail_url)

                    # Category & Location cleanup
                    category = self.categorize(f"{raw_cat} {clean_title}")
                    closing_date = self.parse_sl_date(closing_raw)

                    # Status
                    card_text = it.get_text(' ', strip=True).lower()
                    is_closed = 'closed tender' in card_text
                    status = 'closed' if is_closed else 'open'

                    # Source ID
                    source_id = f"tn_{ref}" if ref else f"tn_{hashlib.md5(detail_url.encode()).hexdigest()[:10]}"

                    # Organization
                    organization = self.extract_organization(clean_title, card_text)

                    # Description
                    desc_parts = [clean_title]
                    if ref:
                        desc_parts.append(f"Reference No: {ref}")
                    if raw_cat:
                        desc_parts.append(f"Category: {raw_cat}")
                    if location:
                        desc_parts.append(f"Location: {location}")
                    if closing_raw:
                        desc_parts.append(f"Closing Date: {closing_raw}")
                    description = "\n".join(desc_parts)

                    tender = {
                        "source_site_id": self.site_id,
                        "source_id": source_id,
                        "title": clean_title,
                        "organization": organization,
                        "published_date": None,
                        "closing_date": closing_date,
                        "location": location,
                        "category": category,
                        "description": description,
                        "document_links": [],
                        "source_url": detail_url,
                        "status": status,
                    }
                    tenders.append(tender)

            except Exception as e:
                print(f"Error scraping page {page} of TenderNotices.lk: {e}")
                break

        self.tenders_found = len(tenders)
        return tenders

