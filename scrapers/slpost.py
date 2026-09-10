from typing import List, Dict
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper

class SLPostScraper(BaseScraper):
    site_id = "slpost"
    site_name = "Sri Lanka Post"
    base_url = "https://slpost.gov.lk"

    def scrape(self) -> List[Dict]:
        tenders = []
        soup = self.fetch_page(f"{self.base_url}/notice/procurement/")
        if not soup:
            return tenders

        page_text = soup.get_text('\n', strip=True)

        # Collect all document links from procurement section
        doc_links_all = []
        processed_titles = set()
        # Find links immediately after bid mentions (WordPress pattern: <p>TITLE <a href="...pdf">- Click here</a></p>)
        for p in soup.find_all(['p', 'div', 'li']):
            p_text = p.get_text(' ', strip=True)
            # Skip navigation/footer/menu items
            if len(p_text) < 20:
                continue
            if any(nav in p_text for nav in ['Home', 'About Us', 'Vision', 'Our Team', 'Services', 'Contact', 'Logo', 'Postal Song', 'Product']):
                if 'Invitation for Bids' not in p_text and 'IFB' not in p_text:
                    continue
            if 'Invitation for Bids' in p_text or 'IFB' in p_text:
                # Skip duplicates
                title_hash = abs(hash(p_text[:200]))
                if title_hash in processed_titles:
                    continue
                processed_titles.add(title_hash)

                links = []
                for a in p.find_all('a', href=True):
                    href = a['href']
                    if href.lower().endswith(('.pdf', '.doc', '.docx')):
                        links.append(href)
                # If no PDF in same paragraph, look in next siblings
                if not links:
                    sibling = p.find_next_sibling()
                    while sibling and len(links) < 3:
                        for a in sibling.find_all('a', href=True):
                            href = a['href']
                            if href.lower().endswith(('.pdf', '.doc', '.docx')):
                                links.append(href)
                        sibling = sibling.find_next_sibling()
                        if sibling and sibling.name in ['h','h2','h3','h4']:
                            break

                # Extract date from PDF URL (WordPress uploads have YYYY/MM in path)
                published_date = None
                if links:
                    date_match = re.search(r'/(\d{4})/(\d{2})/', links[0])
                    if date_match:
                        published_date = f"{date_match.group(1)}-{date_match.group(2)}-01"

                # Categorize
                category = "other"
                p_lower = p_text.lower()
                if any(k in p_lower for k in ['it equipment', 'printer', 'barcode', 'computer', 'software']):
                    category = "IT"
                elif any(k in p_lower for k in ['machine', 'stamp', 'supply', 'deliver']):
                    category = "goods"

                tender = {
                    "source_site_id": self.site_id,
                    "source_id": f"slpost_{title_hash}",
                    "title": p_text[:500],
                    "organization": "Department of Posts, Sri Lanka",
                    "published_date": published_date,
                    "location": "Sri Lanka",
                    "category": category,
                    "document_links": list(set(links)),
                    "source_url": f"{self.base_url}/notice/procurement/#{title_hash}",
                    "status": "open"
                }
                tenders.append(tender)

        # Deduplicate by source_id
        seen = set()
        unique_tenders = []
        for t in tenders:
            if t['source_id'] not in seen:
                seen.add(t['source_id'])
                unique_tenders.append(t)

        self.tenders_found = len(unique_tenders)
        return unique_tenders
