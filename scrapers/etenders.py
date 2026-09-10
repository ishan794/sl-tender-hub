import requests
from datetime import datetime
from typing import List, Dict
from scrapers.base import BaseScraper

class ETendersScraper(BaseScraper):
    """Scraper for eTenders.lk using public API"""
    site_id = "etenders"
    site_name = "eTenders.lk"
    base_url = "https://etenders.lk"
    search_url = "https://api.etenders.lk/api/v1/tender/search"

    def __init__(self):
        super().__init__()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        }

    def infer_category(self, cat_obj_list, title: str) -> str:
        cat_names = " ".join([c.get('name', '').lower() for c in (cat_obj_list or [])])
        combined = f"{cat_names} {title}".lower()
        if any(k in combined for k in ['it', 'software', 'hardware', 'ict', 'computer', 'network']):
            return "it"
        if any(k in combined for k in ['construction', 'civil', 'road', 'building', 'bridge']):
            return "construction"
        if any(k in combined for k in ['transport', 'vehicle', 'car', 'container', 'logistics']):
            return "transport"
        if any(k in combined for k in ['service', 'cleaning', 'security', 'canteen', 'janitorial', 'pest']):
            return "services"
        if any(k in combined for k in ['agriculture', 'fertilizer', 'irrigation', 'crop', 'tea']):
            return "agriculture"
        if any(k in combined for k in ['energy', 'power', 'electrical', 'solar']):
            return "energy"
        return "goods"

    def parse_iso_date(self, dt_str: str) -> str:
        if not dt_str:
            return None
        try:
            # Handle ISO timestamps like 2026-09-08T01:51:13.575+00:00
            clean = dt_str.split('.')[0].replace('Z', '')
            dt = datetime.fromisoformat(clean)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return None

    def scrape(self) -> List[Dict]:
        seen_ids = set()
        tenders = []
        search_terms = ['all', '2026', 'tender', 'supply', 'lanka', 'ministry', 'construction', 'services', 'hospital', 'board', 'bank']
        
        for term in search_terms:
            try:
                url = f"{self.search_url}/{term}"
                r = requests.get(url, headers=self.headers, timeout=12)
                if r.status_code != 200:
                    continue
                data = r.json()
                items = data.get('body', [])
                if not isinstance(items, list):
                    continue
                    
                for t in items:
                    t_id = t.get('id')
                    if not t_id or t_id in seen_ids:
                        continue
                    seen_ids.add(t_id)
                    
                    title = (t.get('title') or '').strip()
                    if not title:
                        continue
                        
                    pub_dt = self.parse_iso_date(t.get('publishedDate') or t.get('createdDate'))
                    close_dt = self.parse_iso_date(t.get('closingDate'))
                    pub_date_only = pub_dt.split(' ')[0] if pub_dt else datetime.now().strftime('%Y-%m-%d')
                    
                    loc = t.get('location') or 'Western Province, Colombo'
                    category = self.infer_category(t.get('category'), title)
                    
                    comp = t.get('company')
                    org = comp.get('name') if isinstance(comp, dict) else (t.get('source') or 'Government of Sri Lanka')
                    
                    val = None
                    if t.get('tenderValue') and float(t['tenderValue']) > 0:
                        val = str(t['tenderValue'])
                        
                    source_url = f"https://etenders.lk/tender/{t_id}"
                    
                    tenders.append({
                        'source_site_id': self.site_id,
                        'source_id': f"et_{t_id}",
                        'title': title,
                        'organization': org,
                        'published_date': pub_date_only,
                        'closing_date': close_dt,
                        'location': loc,
                        'category': category,
                        'estimated_value': val,
                        'currency': 'LKR',
                        'description': title,
                        'eligibility': None,
                        'bid_bond': None,
                        'contact_person': None,
                        'contact_email': None,
                        'contact_phone': None,
                        'collection_address': None,
                        'submission_address': None,
                        'document_fee': None,
                        'pre_bid_meeting': None,
                        'document_links': [],
                        'source_url': source_url,
                        'status': 'open'
                    })
            except Exception as e:
                print(f"[eTenders] Error searching '{term}': {e}")
                continue
                
        self.tenders_found = len(tenders)
        print(f"[{self.site_name}] Scraped {len(tenders)} live tenders")
        return tenders
