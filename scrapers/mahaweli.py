from typing import List, Dict
import re
from urllib.parse import urljoin
from .base import BaseScraper

class MahaweliScraper(BaseScraper):
    site_id = "mahaweli"
    site_name = "Mahaweli Authority"
    base_url = "https://mahaweli.gov.lk"

    def scrape(self) -> List[Dict]:
        tenders = []
        soup = self.fetch_page(f"{self.base_url}/tenders.html")
        if not soup:
            return tenders

        # Collect all BIDDING DOCUMENTS (each is a separate tender)
        # Pattern: <a href="...pdf">Bidding Document - CONTRACT NO: XYZ</a>
        bidding_doc_links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            if text.lower().startswith('bidding document') and href.lower().endswith('.pdf'):
                full_url = urljoin(self.base_url + '/tenders.html', href)
                # Extract contract number
                contract_match = re.search(r'CONTRACT NO:?\s*([A-Z0-9\s\-/.]+)', text, re.IGNORECASE)
                contract_no = contract_match.group(1).strip() if contract_match else None

                # Try to extract date from PDF filename
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', href)
                published_date = self.parse_date(date_match.group(1)) if date_match else None

                # Categorize by contract prefix
                category = "construction"
                if "GOODS" in text.upper():
                    category = "goods"
                if "PROC/GOODS" in href.upper():
                    category = "goods"

                bidding_doc_links.append({
                    "title": text,
                    "contract_no": contract_no,
                    "doc_url": full_url,
                    "published_date": published_date,
                    "category": category
                })

        self.tenders_found = len(bidding_doc_links)

        # Group related BID NOTICE PDFs with their bidding documents
        all_pdfs = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.lower().endswith('.pdf'):
                all_pdfs.append({
                    "text": a.get_text(strip=True),
                    "url": urljoin(self.base_url + '/tenders.html', href)
                })

        for idx, bid_doc in enumerate(bidding_doc_links):
            # Find the nearest notice PDFs (english/sinhala) published around same date
            doc_links = [bid_doc['doc_url']]
            title = bid_doc['title']
            if bid_doc['contract_no']:
                title = f"Tender {bid_doc['contract_no']}: {title}"

            # Use hash of doc URL for guaranteed uniqueness per tender
            import hashlib
            id_hash = hashlib.md5(bid_doc['doc_url'].encode()).hexdigest()[:10]
            source_id = f"mahaweli_{bid_doc['contract_no'].replace(' ','_').replace('/','-') if bid_doc['contract_no'] else id_hash}"

            tender = {
                "source_site_id": self.site_id,
                "source_id": source_id,
                "title": title,
                "organization": "Mahaweli Authority of Sri Lanka",
                "published_date": bid_doc['published_date'],
                "location": "Sri Lanka",
                "category": bid_doc['category'],
                "document_links": doc_links,
                "source_url": f"{self.base_url}/tenders.html#{source_id}",
                "status": "open"
            }
            tenders.append(tender)

        return tenders
