"""
Tenders.lk Private Aggregator Scraper
Uses their official backend API - fastest, most complete source
Collects the FULL history (old + new tenders), not just open/recent ones
"""
from typing import List, Dict
import re
import cloudscraper
from .base import BaseScraper

# Map Tenders.lk categories to our standard categories
CATEGORY_MAP = {
    "Engineering and Construction": "construction",
    "Construction": "construction",
    "Hardware, Machinery and Equipment": "goods",
    "Goods/Supplies": "goods",
    "Services( Financial /Insurance/Janitorial, Security Service etc.,)": "services",
    "Services": "services",
    "IT and Telecom": "IT",
    "Information Technology": "IT",
    "Telecommunication": "IT",
    "Medical and Health Care": "health",
    "Health Care": "health",
    "Pharmaceuticals": "health",
    "Agriculture and Livestock": "agriculture",
    "Agriculture": "agriculture",
    "Livestock": "agriculture",
    "Power and Energy": "energy",
    "Energy": "energy",
    "Electricity": "energy",
    "Education and Training": "education",
    "Education": "education",
    "Training": "education",
    "Transport": "transport",
    "Vehicles": "transport",
    "Supplier Registration": "other",
    "Other": "other",
}

class TendersLKScraper(BaseScraper):
    site_id = "tenders_lk"
    site_name = "Tenders.lk"
    base_url = "https://www.tenders.lk"
    api_base = "https://backend.tenders.lk"

    def __init__(self):
        super().__init__()
        self.scraper = cloudscraper.create_scraper()
        self.scraper.headers.update({
            'Accept': 'application/json',
            'Origin': 'https://www.tenders.lk',
            'Referer': 'https://www.tenders.lk/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.tenders_found = 0
        self.new_tenders = 0

    def map_category(self, cats: List[Dict]) -> str:
        """Map Tenders.lk categories to our standard categories"""
        if not cats:
            return "other"
        cat_str = " ".join([(c.get('name','')+ ' ' + c.get('category_name','')).lower() for c in cats])
        # Prioritize specific categories first
        if any(k in cat_str for k in ['it ', 'telecom', 'information technology']):
            return "IT"
        if 'medical' in cat_str or 'health' in cat_str or 'pharmaceutical' in cat_str:
            return "health"
        if 'agriculture' in cat_str or 'livestock' in cat_str:
            return "agriculture"
        if 'power' in cat_str or 'energy' in cat_str or 'electricity' in cat_str:
            return "energy"
        if 'education' in cat_str or 'training' in cat_str:
            return "education"
        if 'transport' in cat_str or 'vehicle' in cat_str:
            return "transport"
        if 'service' in cat_str or 'consult' in cat_str or 'maintenance' in cat_str:
            return "services"
        if 'engineering' in cat_str or 'construction' in cat_str or 'building' in cat_str:
            return "construction"
        if 'supply' in cat_str or 'goods' in cat_str or 'hardware' in cat_str or 'machinery' in cat_str or 'equipment' in cat_str:
            return "goods"
        for cat in cats:
            name = cat.get('name', '') or cat.get('category_name', '')
            for key, mapped in CATEGORY_MAP.items():
                if key.lower() in name.lower():
                    return mapped
        return "other"

    def extract_organization_from_title(self, title: str) -> str:
        """Try to extract organization name from tender title"""
        # Common patterns: "Ministry of X - Tender title", "Ceylon Electricity Board: IFB for..."
        patterns = [
            r'^(.*?)\s*[–\-:,]\s*(?:\u0DBD\u0D82\u0DC3\u0DD4|invitation|ifb|rfp|bid|procurement|supply|construction|ncb|icb)',
            r'^([A-Z][A-Za-z\.\s&]+)(?:,|\s+[-–:])',
        ]
        for pat in patterns:
            m = re.search(pat, title, re.IGNORECASE)
            if m:
                org = m.group(1).strip()
                if 5 < len(org) < 100:
                    return org
        return None

    def scrape(self) -> List[Dict]:
        tenders = []
        # Collect the FULL history (old + new): paginate through every page until
        # the API returns no more tenders. Closed/expired tenders are kept too.
        from config import MAX_PAGES_PER_SITE
        max_pages = MAX_PAGES_PER_SITE or 100000  # hard safety cap to avoid infinite loops
        page = 1

        while page <= max_pages:
            try:
                url = f"{self.api_base}/api/tenders?page={page}&perPage=15"
                resp = self.scraper.get(url, timeout=10)
                if resp.status_code != 200:
                    break  # error / rate-limited / end of data
                data = resp.json()
                items = data.get('data', [])
                if not items:
                    break  # no more results
                self.tenders_found += len(items)

                for item in items:
                    closing_date = item.get('closing_date')
                    title = item.get('title', '').strip()
                    # Skip empty/supplier registration only notices
                    if not title or len(title) < 10:
                        continue
                    if 'supplier registration' in title.lower():
                        continue

                    published_date = self.parse_date(item.get('published_date') or item.get('created_at'))
                    description = item.get('description', '')
                    # Clean HTML from description
                    if description:
                        from bs4 import BeautifulSoup
                        description = BeautifulSoup(description, 'html.parser').get_text(' ', strip=True)[:2000]

                    # Extract document links
                    doc_links = []
                    if item.get('document'):
                        doc_links.append(item['document'])
                    for doc in item.get('documents', []) or []:
                        if isinstance(doc, str):
                            doc_links.append(doc)
                        elif isinstance(doc, dict) and doc.get('url'):
                            doc_links.append(doc['url'])
                        elif isinstance(doc, dict) and doc.get('file'):
                            doc_links.append(doc['file'])

                    # Keywords for categorization
                    keywords = (item.get('tender_keyword','') or '') + ' ' + (item.get('keywords','') or '')
                    category = self.map_category(item.get('categories', []))
                    # Refine category by keywords if needed
                    full_text = (title + ' ' + keywords).lower()
                    if category == 'other':
                        if any(k in full_text for k in ['construction', 'building', 'road', 'civil']):
                            category = "construction"
                        elif any(k in full_text for k in ['supply', 'goods', 'vehicle', 'equipment', 'printer', 'machine']):
                            category = "goods"
                        elif any(k in full_text for k in ['software', 'computer', 'it ', 'network']):
                            category = "IT"
                        elif any(k in full_text for k in ['service', 'consult', 'maintenance']):
                            category = "services"

                    org_name = self.extract_organization_from_title(title) or "Tenders.lk Listing"

                    # Keep old/closed tenders too — just mark them accurately
                    status = "open"
                    if closing_date:
                        try:
                            from datetime import date
                            cd = date.fromisoformat(str(closing_date)[:10])
                            status = "closed" if cd < date.today() else "open"
                        except Exception:
                            status = "open"

                    tender = {
                        "source_site_id": self.site_id,
                        "source_id": f"tlk_{item.get('tender_code') or item.get('id')}",
                        "title": title[:600],
                        "organization": org_name,
                        "published_date": published_date,
                        "closing_date": closing_date,
                        "location": "Sri Lanka",
                        "category": category,
                        "description": description,
                        "document_links": list(set(doc_links)),
                        "source_url": f"{self.base_url}/tender/{item.get('slug', item['id'])}",
                        "status": status,
                    }
                    tenders.append(tender)

                page += 1

            except Exception as e:
                print(f"    Tenders.lk page {page} error: {e}")
                break

        return tenders
