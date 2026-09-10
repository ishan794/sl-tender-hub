import requests
from datetime import datetime
from typing import List, Dict
from scrapers.base import BaseScraper

class SmartTendersScraper(BaseScraper):
    """Scraper for SmartTenders.lk using official REST API"""
    site_id = "smarttenders"
    site_name = "SmartTenders.lk"
    base_url = "https://smarttenders.lk"
    api_url = "https://admin.smarttenders.lk/api/tenders"

    def __init__(self):
        super().__init__()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        }

    def map_category(self, cats: List[Dict]) -> str:
        if not cats:
            return "goods"
        slugs = [c.get('slug', '').lower() for c in cats]
        names = [c.get('name', '').lower() for c in cats]
        combined = " ".join(slugs + names)
        
        if any(k in combined for k in ['it', 'tech', 'software', 'computer', 'network', 'telecom']):
            return "it"
        if any(k in combined for k in ['construction', 'civil', 'building', 'engineering', 'architect']):
            return "construction"
        if any(k in combined for k in ['transport', 'vehicle', 'automotive', 'logistics']):
            return "transport"
        if any(k in combined for k in ['service', 'cleaning', 'security', 'canteen', 'maintenance']):
            return "services"
        if any(k in combined for k in ['agri', 'food', 'fertilizer', 'irrigation', 'farming']):
            return "agriculture"
        if any(k in combined for k in ['energy', 'power', 'electrical', 'solar']):
            return "energy"
        return "goods"

    def scrape(self) -> List[Dict]:
        tenders = []
        max_pages = 6  # 60 fresh tenders per run
        
        for page in range(1, max_pages + 1):
            try:
                r = requests.get(f"{self.api_url}?page={page}", headers=self.headers, timeout=12)
                if r.status_code != 200:
                    break
                data = r.json()
                t_list = data.get('data', {}).get('tenders', {}).get('data', [])
                if not t_list:
                    break
                    
                for t in t_list:
                    title = (t.get('title') or '').strip()
                    if not title:
                        continue
                        
                    t_id = str(t.get('id') or t.get('code'))
                    code = t.get('code') or t_id
                    pub_date = t.get('date') or datetime.now().strftime('%Y-%m-%d')
                    due_date = t.get('due_date')
                    closing_date = f"{due_date} 23:59:59" if due_date else None
                    
                    loc_parts = []
                    if t.get('province'):
                        loc_parts.append(t['province'].title() + " Province")
                    if t.get('district'):
                        loc_parts.append(t['district'].title())
                    location = ", ".join(loc_parts) if loc_parts else "Western, Colombo"
                    
                    category = self.map_category(t.get('categories', []))
                    
                    doc_links = []
                    if t.get('english_tender_url'):
                        doc_links.append(t['english_tender_url'])
                    if t.get('sinhala_tender_url'):
                        doc_links.append(t['sinhala_tender_url'])
                        
                    source_url = f"{self.base_url}/tenders"
                    
                    tenders.append({
                        'source_site_id': self.site_id,
                        'source_id': f"st_{code}",
                        'title': title,
                        'organization': 'Government of Sri Lanka',
                        'published_date': pub_date,
                        'closing_date': closing_date,
                        'location': location,
                        'category': category,
                        'estimated_value': None,
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
                        'document_links': doc_links,
                        'source_url': f"https://smarttenders.lk/tender/{code}",
                        'status': 'open'
                    })
            except Exception as e:
                print(f"[SmartTenders] Error page {page}: {e}")
                break
                
        self.tenders_found = len(tenders)
        print(f"[{self.site_name}] Scraped {len(tenders)} live tenders")
        return tenders
