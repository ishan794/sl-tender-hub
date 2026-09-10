from typing import List, Dict
import json
from bs4 import BeautifulSoup
from .base import BaseScraper

class TreasuryScraper(BaseScraper):
    site_id = "treasury"
    site_name = "Ministry of Finance Treasury"
    base_url = "https://www.treasury.gov.lk"

    def scrape(self) -> List[Dict]:
        tenders = []

        # Treasury is a Next.js site — all tender data is embedded in __NEXT_DATA__ JSON
        for page in range(1, 4):  # Scrape latest 3 pages
            soup = self.fetch_page(f"{self.base_url}/procurement/procurement-notices?page={page}")
            if not soup:
                continue

            nd = soup.find('script', id='__NEXT_DATA__')
            if not nd:
                continue

            try:
                data = json.loads(nd.string)
                notices = data.get('props', {}).get('pageProps', {}).get('notices', [])
            except Exception:
                continue

            self.tenders_found += len(notices)

            for notice in notices:
                notice_id = notice.get('id')
                title = notice.get('title', '').strip()
                subtitle = notice.get('subtitle', '').strip()
                description = BeautifulSoup(notice.get('description', ''), 'html.parser').get_text(strip=True)

                # Build full title: organization + bidding type + description
                full_title = f"{title} - {subtitle}: {description}" if subtitle else f"{title}: {description}"

                published_date = self.parse_date(notice.get('publishedOn'))
                closing_date = None  # Not directly in list response

                # Extract document links
                doc_links = []
                for att in notice.get('attachments', []):
                    link = att.get('link', '')
                    if link.startswith('http'):
                        doc_links.append(link)
                    elif link:
                        # Attachment UUID — use the direct download URL pattern
                        doc_links.append(f"{self.base_url}/api/attachments/{link}")

                # Categorize based on title/description
                full_text_lower = (full_title + " " + description).lower()
                category = "other"
                if any(k in full_text_lower for k in ['construction', 'work', 'civil', 'building', 'road']):
                    category = "construction"
                elif any(k in full_text_lower for k in ['supply', 'goods', 'procurement of', 'vehicle', 'equipment', 'material']):
                    category = "goods"
                elif any(k in full_text_lower for k in ['it ', 'software', 'computer', 'hardware', 'system']):
                    category = "IT"
                elif any(k in full_text_lower for k in ['consult', 'service', 'maintenance']):
                    category = "services"
                elif 'insurance' in full_text_lower:
                    category = "services"

                tender = {
                    "source_site_id": self.site_id,
                    "source_id": f"treasury_{notice_id}",
                    "title": full_title[:500],  # Truncate long titles
                    "organization": title,
                    "published_date": published_date,
                    "closing_date": closing_date,
                    "location": "Sri Lanka",
                    "category": category,
                    "description": description,
                    "document_links": doc_links,
                    "source_url": f"{self.base_url}/procurement/procurement-notices?page={page}#notice-{notice_id}",
                    "status": "open" if notice.get('status') else "closed"
                }
                tenders.append(tender)

        return tenders
