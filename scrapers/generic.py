"""
Generic Wordpress/Joomla/HTML Tender Scraper
- Full detail extraction (eligibility, contact info, bid bond, deadlines, etc.)
- Strict validation to only collect real tender data (no junk links)
- Works for ~80% of Sri Lankan government/institution websites
"""
from typing import List, Dict
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper

# Strict keyword matching for REAL tender identification
REQUIRED_KEYWORDS = ['tender', 'bid', 'bidding', 'procurement', 'quotation', 'rfp', 'ifb', 'eoi', 'expression of interest', 'invitation for bids', 'request for proposal']
# Junk terms to filter out non-tender pages
EXCLUDE_KEYWORDS = ['tender result', 'awarded', 'cancelled tender', 'archived tender', 'login', 'register', 'sign in', 'terms and conditions', 'supplier registration', 'download', 'gallery', 'news', 'vacancy']
# Minimum title length to be considered a valid tender (avoids junk menu items)
MIN_TITLE_LENGTH = 25
# Maximum title length (truncate extremely long spam)
MAX_TITLE_LENGTH = 600

# Regex patterns for extracting detailed fields from page text
DATE_PATTERNS = [
    (r'published\s*(?:on|date)?\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})', 'published'),
    (r'closing\s*(?:on|date|time)?\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}(?:\s+\d{1,2}:\d{2})?)', 'closing'),
    (r'due\s*(?:on|date)?\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})', 'closing'),
    (r'submission\s*(?:deadline|date|on|by)?\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})', 'closing'),
    (r'bid\s*closing\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})', 'closing'),
    (r'pre[- ]?bid\s*meeting\s*(?:on|date)?\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})', 'pre_bid'),
    (r'pre[- ]?proposal\s*conference\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})', 'pre_bid'),
]
MONEY_PATTERNS = [
    r'(?:estimated|contract|bid)\s*value\s*:?\s*(?:Rs\.?|LKR|USD)?\s*([0-9,.]+\s*(?:million|billion|LKR|Rs\.?|lakhs|crore)?)',
    r'bid\s*bond\s*(?:amount|security)?\s*:?\s*(?:Rs\.?|LKR|USD)?\s*([0-9,.]+\s*(?:million|billion|LKR|Rs\.?|lakhs|crore)?)',
    r'bid\s*security\s*:?\s*(?:Rs\.?|LKR|USD)?\s*([0-9,.]+\s*(?:million|billion|LKR|Rs\.?|lakhs|crore)?)',
    r'document\s*fee\s*:?\s*(?:Rs\.?|LKR|USD)?\s*([0-9,.]+\s*(?:million|billion|LKR|Rs\.?|lakhs|crore)?)',
    r'non[- ]?refundable\s*fee\s*:?\s*(?:Rs\.?|LKR|USD)?\s*([0-9,.]+\s*(?:million|billion|LKR|Rs\.?|lakhs|crore)?)',
]
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'(?:\+94|0)?[0-9]{9,10}'
CURRENCY_PATTERN = r'(USD|LKR|Rs\.?|\$|\u0DBB\u0DD4)'

class GenericScraper(BaseScraper):
    def __init__(self, source_id: str, name: str, base_url: str, tender_url: str, strategy: str = "generic_wp"):
        super().__init__()
        self.site_id = source_id
        self.site_name = name
        self.base_url = base_url
        self.tender_url = tender_url or base_url
        self.strategy = strategy

    def is_valid_tender(self, text: str, href: str = "") -> bool:
        """Strict validation to only keep REAL tender notices, filter junk/menu items/other links"""
        combined = (text + " " + href).lower()
        # Must contain at least one required tender keyword
        if not any(kw in combined for kw in REQUIRED_KEYWORDS):
            return False
        # Exclude known junk pages
        if any(exc in combined for exc in EXCLUDE_KEYWORDS):
            return False
        # Title length check
        if len(text.strip()) < MIN_TITLE_LENGTH or len(text.strip()) > MAX_TITLE_LENGTH:
            return False
        # Exclude common navigation/menu items
        nav_patterns = ['click here', 'read more', 'view all', 'see more', 'download tender', 'home', 'about us', 'contact us', 'sitemap']
        if combined.strip() in nav_patterns:
            return False
        return True

    def categorize(self, text: str) -> str:
        text = text.lower()
        # Important: Check IT/services/specialized categories BEFORE goods/construction
        if any(k in text for k in ['it ', 'software', 'hardware', 'system', 'network', 'website', 'digital', 'server', 'laptop', 'computer', 'software development']):
            return "IT"
        elif any(k in text for k in ['health', 'medical', 'medicine', 'hospital', 'pharmaceutical', 'drug', 'vaccine']):
            return "health"
        elif any(k in text for k in ['agriculture', 'seed', 'fertilizer', 'livestock', 'fisheries', 'paddy']):
            return "agriculture"
        elif any(k in text for k in ['energy', 'electricity', 'power', 'solar', 'transformer', 'generator', 'electric']):
            return "energy"
        elif any(k in text for k in ['education', 'university', 'school', 'training', 'book', 'scholarship']):
            return "education"
        elif any(k in text for k in ['transport', 'bus', 'van', 'lorry', 'railway', 'vehicle']):
            return "transport"
        elif any(k in text for k in ['consult', 'service', 'maintenance', 'security', 'cleaning', 'insurance', 'audit', 'transport service', 'catering']):
            return "services"
        elif any(k in text for k in ['construction', 'work', 'civil', 'building', 'road', 'irrigation', 'asphalt', 'building construction']):
            return "construction"
        elif any(k in text for k in ['supply', 'goods', 'vehicle', 'equipment', 'machine', 'material', 'printer', 'furniture', 'stationery', 'fuel', 'chemical']):
            return "goods"
        return "other"

    def extract_details_from_page(self, soup: BeautifulSoup, full_text: str) -> Dict:
        """Extract all detailed tender fields from the page content"""
        details = {
            "description": None,
            "estimated_value": None,
            "bid_bond": None,
            "document_fee": None,
            "pre_bid_meeting": None,
            "contact_email": None,
            "contact_phone": None,
            "contact_person": None,
            "eligibility": None,
            "currency": "LKR",
        }

        # Extract dates
        for pattern, field in DATE_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                parsed = self.parse_date(match.group(1))
                if parsed:
                    if field == 'published':
                        details.setdefault('published_date', parsed)
                    elif field == 'closing':
                        details.setdefault('closing_date', parsed)
                    elif field == 'pre_bid':
                        details['pre_bid_meeting'] = parsed

        # Extract money fields
        money_matches = re.findall(MONEY_PATTERNS[0], full_text, re.IGNORECASE)
        if money_matches:
            details['estimated_value'] = money_matches[0].strip()
        bond_matches = re.findall(MONEY_PATTERNS[1], full_text, re.IGNORECASE) + re.findall(MONEY_PATTERNS[2], full_text, re.IGNORECASE)
        if bond_matches:
            details['bid_bond'] = bond_matches[0].strip()
        fee_matches = re.findall(MONEY_PATTERNS[3], full_text, re.IGNORECASE) + re.findall(MONEY_PATTERNS[4], full_text, re.IGNORECASE)
        if fee_matches:
            details['document_fee'] = fee_matches[0].strip()

        # Currency detection
        if re.search(r'USD|\$', full_text):
            details['currency'] = "USD"

        # Contact email
        emails = re.findall(EMAIL_PATTERN, full_text)
        if emails:
            details['contact_email'] = emails[0]

        # Phone numbers
        phones = re.findall(PHONE_PATTERN, full_text)
        # Filter out invalid/too short numbers
        valid_phones = [p for p in phones if len(p) >= 9]
        if valid_phones:
            details['contact_phone'] = valid_phones[0]

        # Extract main description (first large paragraph after title)
        main_content = soup.find(['div', 'article'], class_=re.compile(r'content|entry|post|detail|description|procurement', re.I))
        if main_content:
            paras = main_content.find_all('p')
            desc_text = []
            for p in paras:
                t = p.get_text(' ', strip=True)
                if 30 < len(t) < 2000:
                    desc_text.append(t)
            if desc_text:
                details['description'] = '\n'.join(desc_text[:3])[:2000]  # First 3 paragraphs max
        else:
            # Fallback: first long paragraph on page
            for p in soup.find_all('p'):
                t = p.get_text(' ', strip=True)
                if len(t) > 80:
                    details['description'] = t[:2000]
                    break

        # Extract eligibility criteria
        elig_section = re.search(
            r'(?:eligibility\s*(?:criteria|requirements)?|qualified\s*bidders?|bidd?er?\s*shall)\s*:?\s*([^\n]{20,500})',
            full_text, re.IGNORECASE
        )
        if elig_section:
            details['eligibility'] = elig_section.group(1).strip()[:1000]

        # Extract contact person
        contact_match = re.search(
            r'(?:contact\s*(?:person|officer)?|procurement\s*officer)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            full_text
        )
        if contact_match:
            details['contact_person'] = contact_match.group(1).strip()

        return details

    def _collect_page_links(self, soup, base_url: str) -> List[tuple]:
        """Find all tender-looking links on a listing page (deduplicated)."""
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(' ', strip=True)
            if not text or len(text) < MIN_TITLE_LENGTH:
                continue
            # Filter junk URLs
            if any(x in href.lower() for x in ['javascript:', '#', 'mailto:', 'login', 'register']):
                continue
            if self.is_valid_tender(text, href):
                full_url = urljoin(base_url, href)
                if full_url not in self._seen_urls:
                    self._seen_urls.add(full_url)
                    links.append((text.strip(), full_url))
        return links

    def _pagination_urls(self, base_url: str, page: int) -> List[str]:
        """Candidate URLs for the nth page of a listing (WordPress/Joomla/plain)."""
        if page <= 1:
            return [base_url]
        variants = []
        if self.strategy == "joomla":
            variants.append(f"{base_url}{'&' if '?' in base_url else '?'}start={(page - 1) * 10}")
        if '?' in base_url:
            variants.append(f"{base_url}&page={page}")
            variants.append(f"{base_url}&paged={page}")
        else:
            variants.append(f"{base_url}?page={page}")
            variants.append(f"{base_url}?paged={page}")
            variants.append(base_url.rstrip('/') + f"/page/{page}/")
        return variants

    def scrape(self) -> List[Dict]:
        tenders = []
        self._seen_urls = set()

        from config import MAX_PAGES_PER_SITE, MAX_TENDERS_PER_SITE
        max_pages = MAX_PAGES_PER_SITE or 200  # listing-pagination safety cap
        max_tenders = MAX_TENDERS_PER_SITE  # None = collect everything

        # Try common tender page URL patterns if direct page fails
        urls_to_try = [self.tender_url]
        if self.strategy == "discover":
            # For sites without known tender page, try common paths
            common_paths = ['/tenders', '/procurement', '/tender-notices', '/notices/procurement',
                            '/tenders.html', '/web/index.php/tenders', '/media/tenders', '/en/tenders',
                            '/tender', '/notice/tenders', '/procurement-notices']
            urls_to_try = [urljoin(self.base_url, path) for path in common_paths]

        for base_url in urls_to_try:
            try:
                page = 1
                empty_pages = 0

                while page <= max_pages:
                    # Resolve this listing page (try pagination variants in order)
                    soup = None
                    current_url = base_url
                    for candidate in self._pagination_urls(base_url, page):
                        soup = self.fetch_page(candidate)
                        if soup:
                            current_url = candidate
                            break
                    if not soup:
                        break

                    tender_links = self._collect_page_links(soup, current_url)
                    self.tenders_found += len(tender_links)

                    if not tender_links:
                        empty_pages += 1
                        if empty_pages >= 2:  # two empty pages in a row => end of listings
                            break
                        page += 1
                        continue
                    empty_pages = 0

                    if max_tenders is not None:
                        remaining = tender_links[:max_tenders - len(tenders)]
                    else:
                        remaining = tender_links

                    for title, detail_url in remaining:
                        published_date = None
                        closing_date = None
                        doc_links = []
                        extra_details = {}

                        # Clean title (remove extra whitespace/newlines)
                        title = re.sub(r'\s+', ' ', title).strip()[:MAX_TITLE_LENGTH]

                        # For direct PDF links - don't fetch detail page
                        if detail_url.lower().endswith(('.pdf', '.doc', '.docx')):
                            doc_links = [detail_url]
                            # Try to extract date from URL path
                            date_match = re.search(r'/(\d{4})/(\d{2})/', detail_url)
                            if date_match:
                                published_date = f"{date_match.group(1)}-{date_match.group(2)}-01"
                        else:
                            # Fetch detail page for full information
                            try:
                                detail_soup = self.fetch_page(detail_url)
                                if detail_soup:
                                    full_text = detail_soup.get_text(' ', strip=True)
                                    full_text = re.sub(r'\s+', ' ', full_text)

                                    # Extract all detailed fields
                                    extra_details = self.extract_details_from_page(detail_soup, full_text)
                                    published_date = extra_details.pop('published_date', None)
                                    closing_date = extra_details.pop('closing_date', None)

                                    # Extract all document links (PDF/DOC/XLSX)
                                    for a in detail_soup.find_all('a', href=True):
                                        dhref = a['href']
                                        if dhref.lower().endswith(('.pdf', '.doc', '.docx', '.xlsx', '.zip')):
                                            full_doc_url = urljoin(detail_url, dhref)
                                            doc_links.append(full_doc_url)

                                    # Get better title from detail page if available
                                    h1 = detail_soup.find(['h1', 'h2'], class_=re.compile(r'title|heading', re.I))
                                    if not h1:
                                        h1 = detail_soup.find('h1')
                                    if h1:
                                        h1_text = h1.get_text(' ', strip=True)
                                        if MIN_TITLE_LENGTH < len(h1_text) < MAX_TITLE_LENGTH:
                                            # Make sure it's actually a tender
                                            if self.is_valid_tender(h1_text):
                                                title = h1_text
                            except Exception:
                                pass

                        # Mark old/closed tenders accurately instead of dropping them
                        status = "open"
                        if closing_date:
                            try:
                                from datetime import date
                                cd = date.fromisoformat(str(closing_date)[:10])
                                status = "closed" if cd < date.today() else "open"
                            except Exception:
                                status = "open"

                        # Generate unique ID from URL
                        import hashlib
                        source_id = f"{self.site_id}_{hashlib.md5(detail_url.encode()).hexdigest()[:10]}"

                        tender = {
                            "source_site_id": self.site_id,
                            "source_id": source_id,
                            "title": title,
                            "organization": self.site_name,
                            "published_date": published_date,
                            "closing_date": closing_date,
                            "location": "Sri Lanka",
                            "category": self.categorize(title + " " + str(extra_details.get('description', ''))),
                            "document_links": list(set(doc_links)),
                            "source_url": detail_url,
                            "status": status,
                            **extra_details
                        }
                        tenders.append(tender)

                    if max_tenders is not None and len(tenders) >= max_tenders:
                        break

                    page += 1

                if tenders:
                    break  # Got results from this URL pattern, no need to try other paths
            except Exception:
                continue

        return tenders
