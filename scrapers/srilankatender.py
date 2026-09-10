import re
from datetime import datetime
from typing import List, Dict
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper

class SriLankaTenderScraper(BaseScraper):
    """Scraper for SriLankaTender.com"""
    site_id = "srilankatender"
    site_name = "SriLankaTender.com"
    base_url = "https://www.srilankatender.com"

    def __init__(self):
        super().__init__()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

    def infer_category(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ['software', 'computer', 'server', 'network', 'cctv', 'ict', 'hardware', 'laptop']):
            return "it"
        if any(k in t for k in ['hospital', 'medical', 'medicine', 'surgical', 'drug', 'pharmaceutical']):
            return "services"
        if any(k in t for k in ['construction', 'building', 'rehabilitation', 'renovation', 'road', 'civil', 'bridge']):
            return "construction"
        if any(k in t for k in ['vehicle', 'transport', 'car', 'bus', 'fuel', 'hire', 'rental']):
            return "transport"
        if any(k in t for k in ['janitorial', 'security', 'cleaning', 'consultant', 'maintenance', 'catering', 'canteen']):
            return "services"
        if any(k in t for k in ['tea', 'fertilizer', 'agriculture', 'irrigation', 'paddy', 'crop']):
            return "agriculture"
        return "goods"

    def scrape(self) -> List[Dict]:
        tenders = []
        # Collect the FULL history: paginate until no more tender cards are found.
        from config import MAX_PAGES_PER_SITE
        max_pages = MAX_PAGES_PER_SITE or 100000  # safety cap
        page = 1

        while page <= max_pages:
            url = f"{self.base_url}/tenders.php?page={page}" if page > 1 else f"{self.base_url}/tenders.php"
            soup = self.fetch_page(url)
            if not soup:
                break

            cards = soup.find_all('div', class_='tender-card')
            if not cards:
                break

            page_found = 0
            for c in cards:
                try:
                    txt = c.get_text(' | ', strip=True)
                    link = c.find('a', href=lambda h: h and '/tender/' in h)
                    if not link:
                        continue
                    
                    href = link['href']
                    source_url = (self.base_url + href) if href.startswith('/') else href
                    
                    # Extract source ID from URL
                    m_id = re.search(r'/tender/([A-Za-z0-9\-_]+)', href)
                    source_id = m_id.group(1) if m_id else f"slt_{len(tenders) + 1}"
                    
                    title_el = c.find(['h2', 'h3', 'h4']) or link
                    title = title_el.get_text(strip=True) if title_el else ''
                    if not title:
                        continue
                        
                    # Ref
                    m_ref = re.search(r'(?:LKT\s*Ref\s*No\.?|Ref\s*No\.?):\s*([A-Za-z0-9\-_/]+)', txt, re.IGNORECASE)
                    ref = m_ref.group(1).strip() if m_ref else source_id
                    
                    # Closing date
                    m_date = re.search(r'Deadline:\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', txt, re.IGNORECASE)
                    closing_date = None
                    if m_date:
                        try:
                            closing_date = datetime.strptime(m_date.group(1).strip(), '%d %b %Y').strftime('%Y-%m-%d 23:59:59')
                        except Exception:
                            pass
                            
                    # Organization
                    m_org = re.search(r'(?:Purchaser|Authority|Department|Ministry|Client):\s*([^|]+)', txt, re.IGNORECASE)
                    org = m_org.group(1).strip() if m_org else "Government of Sri Lanka"
                    
                    category = self.infer_category(title + " " + txt)

                    # Keep old/closed tenders too — mark status from the deadline
                    status = "open"
                    if closing_date:
                        try:
                            from datetime import date
                            cd = date.fromisoformat(str(closing_date)[:10])
                            status = "closed" if cd < date.today() else "open"
                        except Exception:
                            status = "open"

                    tenders.append({
                        'source_site_id': self.site_id,
                        'source_id': source_id,
                        'title': title,
                        'organization': org,
                        'published_date': datetime.now().strftime('%Y-%m-%d'),
                        'closing_date': closing_date,
                        'location': 'Western, Colombo',
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
                        'document_links': [],
                        'source_url': source_url,
                        'status': status
                    })
                    page_found += 1
                except Exception as e:
                    continue

            if page_found == 0:
                break

            page += 1

        self.tenders_found = len(tenders)
        print(f"[{self.site_name}] Scraped {len(tenders)} tenders (full history)")
        return tenders
