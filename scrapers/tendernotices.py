"""
TenderNotices.lk Scraper (Tender Alert Service)
Public listing: /tenders-sri-lanka  -> 40,000+ tenders (old + new).

Detail pages redirect to /login, so Organization / Source / Published Date are
hidden behind a paid login. Everything visible on the listing is collected:
title, category, location, closing date, reference no, and live/closed status.

The previous scraper used selectors (div.tender, .tender-detals) that no longer
match the live site, which is why 0 tenders were being collected. This version
parses cards by their /tender/{REF} links and labeled fields, so it is robust to
markup changes.
"""
from typing import List, Dict
import re
from datetime import datetime
from bs4 import BeautifulSoup
from .base import BaseScraper

# Labels that appear on each tender card, in order. Used to split card text
# into fields reliably without depending on CSS class names.
FIELD_LABELS = ['Category', 'Source', 'Location', 'Published Date', 'Closing Date', 'Reference No']
HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

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

    @staticmethod
    def _has(text: str, keywords) -> bool:
        """Match multi-word phrases as substrings; single words as whole words
        (so 'atm' doesn't match inside 'treatment', 'it' inside 'security', etc.)."""
        for k in keywords:
            if ' ' in k or '-' in k:
                if k in text:
                    return True
            else:
                if re.search(r'\b' + re.escape(k) + r'\b', text):
                    return True
        return False

    def categorize(self, text: str) -> str:
        t = text.lower()
        if self._has(t, ['computer', 'software', 'network', 'server', 'website',
                         'laptop', 'printer', 'scanner', 'pabx', 'wifi', 'firewall',
                         'ict', 'cctv', 'router', 'switch', 'database', 'mobile app',
                         'os & it', 'it support', 'it equipment']):
            return "IT"
        if self._has(t, ['medical', 'pharmaceutical', 'hospital', 'surgical', 'laboratory',
                         'medicine', 'health', 'ambulance', 'dental', 'drug']):
            return "health"
        if self._has(t, ['construction', 'building', 'civil', 'road', 'bridge', 'drain',
                         'sewerage', 'renovation', 'rehabilitation', 'fence', 'roof',
                         'ceiling', 'plumbing', 'waterproof', 'painting', 'partition',
                         'aluminium', 'architecture', 'carpeting', 'flooring',
                         'water supply']):
            return "construction"
        if self._has(t, ['cleaning', 'janitorial', 'security', 'manpower', 'consultancy',
                         'audit', 'tax', 'insurance', 'catering', 'service', 'maintenance',
                         'printing', 'advertising', 'courier', 'logistics', 'laundry',
                         'rent', 'lease', 'hire', 'removal', 'canteen', 'pest', 'supplier',
                         'registration']):
            return "services"
        if self._has(t, ['vehicle', 'vehicles', 'car', 'cars', 'bus', 'buses',
                         'lorry', 'lorries', 'auto', 'autos', 'boat', 'boats',
                         'rent a car', 'logistics', 'transport']):
            return "transport"
        if self._has(t, ['electrical', 'electronic', 'solar', 'generator', 'power', 'energy',
                         'transformer', 'boiler', 'light', 'chiller', 'fire detection',
                         'mep', 'elv']):
            return "energy"
        if self._has(t, ['agriculture', 'farming', 'seed', 'fertilizer', 'livestock',
                         'crop', 'animal', 'fisheries']):
            return "agriculture"
        if self._has(t, ['education', 'training', 'vocational', 'school', 'university']):
            return "education"
        if self._has(t, ['furniture', 'stationery', 'hardware', 'equipment', 'machinery',
                         'food', 'beverage', 'textile', 'fashion', 'plastic', 'rubber',
                         'chemical', 'gift', 'kitchen', 'battery', 'packing', 'sport',
                         'material', 'spare parts']):
            return "goods"
        return "other"

    def _find_card(self, anchor):
        """Walk up from a /tender/{REF} link to find its card container.

        The card is the smallest ancestor that contains a single tender's fields
        ('Closing Date' + 'Reference No'), preferring one that also holds the title
        heading.
        """
        node = anchor
        candidates = []
        for _ in range(12):
            if node is None:
                break
            txt = node.get_text(' ', strip=True)
            if 'Closing Date' in txt and 'Reference No' in txt:
                candidates.append(node)
            node = node.parent
        if not candidates:
            return anchor
        # Prefer smallest container with exactly one reference number and a heading
        for c in candidates:
            txt = c.get_text(' ', strip=True)
            if txt.count('Reference No') == 1 and c.find(HEADING_TAGS):
                return c
        # Otherwise smallest container with exactly one reference number
        for c in candidates:
            if c.get_text(' ', strip=True).count('Reference No') == 1:
                return c
        return candidates[0]

    def _field_value(self, text: str, label: str):
        """Extract the value after 'Label:' up to the next known label."""
        m = re.search(re.escape(label) + r'\s*:', text)
        if not m:
            return None
        start = m.end()
        end = len(text)
        for other in FIELD_LABELS:
            if other == label:
                continue
            om = re.search(re.escape(other) + r'\s*:', text[start:])
            if om:
                end = min(end, start + om.start())
        return text[start:end].strip() or None

    def _parse_card(self, ref: str, card):
        text = re.sub(r'\s+', ' ', card.get_text(' ', strip=True))

        h = card.find(HEADING_TAGS)
        title = h.get_text(' ', strip=True) if h else None
        if not title or len(title) < 8:
            # fallback: first long anchor text that isn't a login/click link
            for a in card.find_all('a'):
                t = a.get_text(' ', strip=True)
                if len(t) > 15 and 'login' not in t.lower() and 'click' not in t.lower():
                    title = t
                    break
        if not title:
            return None
        title = re.sub(r'\s+', ' ', title).strip()[:600]

        category_raw = self._field_value(text, 'Category') or ''
        location = self._field_value(text, 'Location')
        closing_raw = self._field_value(text, 'Closing Date')

        ref_m = re.search(r'Reference\s*No\.?:?\s*([A-Z0-9_-]+)', text, re.I)
        ref_no = ref_m.group(1) if ref_m else ref

        closing_date = self.parse_sl_date(closing_raw) if closing_raw else None
        low = text.lower()
        status = 'closed' if 'closed tender' in low else 'open'

        return {
            'source_site_id': self.site_id,
            'source_id': f"tn_{ref_no}",
            'title': title,
            'organization': None,       # hidden behind login on the public site
            'published_date': None,     # hidden behind login
            'closing_date': closing_date,
            'location': location,
            'category': self.categorize(f"{category_raw} {title}"),
            'description': None,
            'document_links': [],
            'source_url': f"{self.base_url}/tender/{ref_no}",
            'status': status,
            'source_name': 'TenderNotices.lk',
        }

    def scrape(self, max_pages: int = None) -> List[Dict]:
        tenders = []
        seen_refs = set()

        # Collect the FULL history: paginate until no more tender listings appear.
        if max_pages is None:
            from config import MAX_PAGES_PER_SITE
            max_pages = MAX_PAGES_PER_SITE or 100000  # safety cap

        detail_re = re.compile(r'/tender/([A-Za-z0-9_-]+)', re.I)

        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/tenders-sri-lanka?page={page}"
            soup = self.fetch_page(url)
            if not soup:
                break

            # Group every /tender/{REF} link by its reference number (each card
            # has several links pointing to the same detail URL).
            anchors = {}
            order = []
            for a in soup.find_all('a', href=True):
                m = detail_re.search(a['href'])
                if not m:
                    continue
                ref = m.group(1)
                if ref not in anchors:
                    anchors[ref] = a
                    order.append(ref)

            if not order:
                break  # no tender cards -> end of listings

            page_parsed = 0
            for ref in order:
                if ref in seen_refs:
                    continue
                seen_refs.add(ref)
                card = self._find_card(anchors[ref])
                t = self._parse_card(ref, card)
                if t:
                    tenders.append(t)
                    page_parsed += 1

            # Stop early if a page yields no new cards (past the last page)
            if page_parsed == 0 and page > 1:
                break

        self.tenders_found = len(tenders)
        print(f"[{self.site_name}] Scraped {len(tenders)} tenders")
        return tenders
