"""
AuthenticatedScraper - base class for tender websites that need a LOGIN.

Public sites (mahaweli, slpost, treasury, ...) use BaseScraper. Sites that
hide their tender data behind an e-mail + password use this class instead.

What it gives you:
  * session with cookies (saved between runs -> fewer logins, less blocking)
  * 4 login styles: HTML form, JSON API + token, bearer token, HTTP basic
  * CSRF / hidden field handling (tokens on the login form are carried over)
  * automatic re-login when the session expires mid-run
  * pagination ({page} template or ?page=1,2,3 ...) until the site runs out
  * row -> tender mapping with CSS selectors AND automatic detection
  * full-detail extraction on every notice page (dates, contacts, documents)
  * optional download of tender documents (PDF/DOC/XLS)
  * output already shaped for database.insert_tender()

Everything site-specific comes from credentials.SiteCredentials, so a new
private portal is normally just a few lines in credentials.py.
"""
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import cloudscraper
from bs4 import BeautifulSoup, Tag

import config
from credentials import SiteCredentials
from .base import BaseScraper
from .generic import (
    DATE_PATTERNS,
    EMAIL_PATTERN,
    EXCLUDE_KEYWORDS,
    MAX_TITLE_LENGTH,
    MIN_TITLE_LENGTH,
    MONEY_PATTERNS,
    PHONE_PATTERN,
    REQUIRED_KEYWORDS,
    categorize_text,
)

CLOSING_PATTERNS = [p for p, kind in DATE_PATTERNS if kind == "closing"]
PUBLISHED_PATTERNS = [p for p, kind in DATE_PATTERNS if kind == "published"]
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".ppt", ".pptx")


class LoginError(Exception):
    """Raised when the site rejects the login details."""


class AuthenticatedScraper(BaseScraper):
    """Base scraper for login-protected tender portals."""

    #: run_scraper.py skips the site (instead of failing) when this is True
    #: and no credentials are configured yet.
    requires_credentials = True

    def __init__(self, creds: Optional[SiteCredentials] = None):
        super().__init__()
        self.creds: SiteCredentials = creds or self.default_credentials()
        if self.creds is None:
            raise ValueError("No credentials supplied for this authenticated scraper")

        self.site_id = self.creds.site_id or self.site_id or "my_tender_site"
        self.site_name = self.creds.site_name or self.site_name or "My Tender Site"
        self.base_url = self.creds.site_url or self.base_url

        # Reuse the cloudscraper session created by BaseScraper as our session:
        # it keeps cookies, follows redirects and copes with Cloudflare.
        self.session = self.scraper
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.timeout = config.AUTH_REQUEST_TIMEOUT
        self.max_retries = max(1, config.AUTH_MAX_RETRIES)

        self.logged_in = False
        self.auth_token_value: Optional[str] = None
        self.login_url = self.creds.login_url or self._guess_login_url()
        self.login_attempts = 0
        self._login_error: Optional[str] = None
        self._seen_titles: List[str] = []
        self._cookies_path: Optional[Path] = self._cookies_file()

    # ==================================================================
    # Class level helpers used by run_scraper.py
    # ==================================================================
    @classmethod
    def default_credentials(cls) -> Optional[SiteCredentials]:
        """Credentials used when none are passed in - override in subclasses."""
        try:
            from credentials import MY_SITE
        except Exception:
            return None
        return MY_SITE

    @classmethod
    def credentials_ready(cls) -> bool:
        """True when the site can actually be scraped (pointers filled in)."""
        try:
            creds = cls.default_credentials()
        except Exception:
            return False
        return bool(creds and creds.is_complete)

    # ==================================================================
    # HTTP plumbing (session aware, retries, polite delay)
    # ==================================================================
    def _request(self, method: str, url: str, **kwargs) -> Optional[object]:
        """One HTTP call with retries. Returns a Response or None."""
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("allow_redirects", True)
        last_error = None
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.creds.polite_delay)
                response = self.session.request(method, url, **kwargs)
                if response.status_code in (401, 403) and self.creds.auth_method == "token":
                    print(f"    ⚠️  {response.status_code} on {url} - check the API token")
                    return response
                return response
            except Exception as exc:  # noqa: BLE001 - report and retry
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        print(f"    ❌ {method.upper()} {url} failed: {last_error}")
        return None

    def get(self, url: str, **kwargs):
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self._request("POST", url, **kwargs)

    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        response = self.get(url)
        if response is None or response.status_code != 200:
            return None
        return BeautifulSoup(response.text, "html.parser")

    def get_json(self, url: str) -> Optional[dict]:
        response = self.get(url, headers={"Accept": "application/json"})
        if response is None or response.status_code != 200:
            return None
        try:
            return response.json()
        except ValueError:
            print(f"    ⚠️  {url} did not return JSON")
            return None

    # ==================================================================
    # LOGIN
    # ==================================================================
    def _guess_login_url(self) -> str:
        if not self.base_url:
            return ""
        return urljoin(self.base_url.rstrip("/") + "/", "login")

    def login(self, force: bool = False) -> bool:
        """Log in to the site. Returns True on success."""
        if self.logged_in and not force:
            return True
        if not self.creds.is_complete:
            missing = ", ".join(self.creds.missing)
            raise LoginError(f"Login details missing for {self.site_name}: {missing}")

        if not force and self._load_cookies() and self._verify_session():
            self.logged_in = True
            print(f"    🔑 {self.site_name}: reusing saved login session")
            return True

        method = (self.creds.auth_method or "form").lower()
        if method == "form":
            ok = self._login_form()
        elif method == "json":
            ok = self._login_json()
        elif method == "token":
            ok = self._login_token()
        elif method == "basic":
            ok = self._login_basic()
        else:
            raise LoginError(f"Unknown auth_method '{self.creds.auth_method}'")

        self.login_attempts += 1
        if ok:
            self.logged_in = True
            self._login_error = None
            self._save_cookies()
            print(f"    🔑 {self.site_name}: logged in as {self.creds.login_email or 'token'}")
        else:
            self.logged_in = False
            raise LoginError(self._login_error or f"Login failed for {self.site_name}")
        return True

    # ---- HTML form login ------------------------------------------------
    def _login_form(self) -> bool:
        soup = self.get_soup(self.login_url)
        if soup is None:
            self._login_error = f"Login page not reachable: {self.login_url}"
            return False

        form = self._find_login_form(soup)
        action = self.login_url
        if form is not None:
            action = urljoin(self.login_url, form.get("action") or "")

        payload = self._hidden_fields(form)
        email_field = self.creds.email_field or self._detect_email_field(form)
        password_field = self.creds.password_field or self._detect_password_field(form)
        if not password_field:
            self._login_error = (
                f"No password box found on {self.login_url} - "
                "set password_field / email_field in credentials.py"
            )
            return False
        email_field = email_field or "email"
        payload[email_field] = self.creds.login_email
        payload[password_field] = self.creds.login_password
        payload.update(self.creds.login_payload_extra or {})

        response = self.post(
            action,
            data=payload,
            headers={"Referer": self.login_url, "Origin": urlparse(self.login_url).scheme + "://" + urlparse(self.login_url).netloc},
        )
        return self._verify_login(response)

    def _find_login_form(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Pick the form that has a password box (the real login form)."""
        for form in soup.find_all("form"):
            if form.find("input", {"type": "password"}):
                return form
        # Some sites have no <form> tag: fall back to any form that exists
        forms = soup.find_all("form")
        return forms[0] if forms else None

    @staticmethod
    def _hidden_fields(form: Optional[Tag]) -> Dict[str, str]:
        """Collect hidden inputs (CSRF tokens, _token, form_build_id, ...)."""
        fields: Dict[str, str] = {}
        if form is None:
            return fields
        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not name:
                continue
            tag_type = (tag.get("type") or "").lower()
            if tag_type == "submit":
                continue
            if tag_type == "hidden" or tag.has_attr("value"):
                fields[name] = tag.get("value", "")
        return fields

    @staticmethod
    def _detect_email_field(form: Optional[Tag]) -> Optional[str]:
        if form is None:
            return None
        emailish = re.compile(r"(e[-_ ]?mail|user|login|username|nic|account)", re.I)
        for tag in form.find_all("input"):
            if (tag.get("type") or "").lower() == "email" and tag.get("name"):
                return tag["name"]
        for tag in form.find_all("input"):
            name = tag.get("name") or ""
            if name and emailish.search(name) and (tag.get("type") or "").lower() != "password":
                return name
        return None

    @staticmethod
    def _detect_password_field(form: Optional[Tag]) -> Optional[str]:
        if form is None:
            return None
        tag = form.find("input", {"type": "password"})
        return tag.get("name") if tag and tag.get("name") else None

    # ---- JSON / API login ----------------------------------------------
    def _login_json(self) -> bool:
        url = self.creds.login_api_url or urljoin(self.base_url.rstrip("/") + "/", "api/login")
        payload = dict(self.creds.login_payload_extra or {})
        payload.setdefault("email", self.creds.login_email)
        payload.setdefault("password", self.creds.login_password)
        response = self.post(url, json=payload, headers={"Accept": "application/json"})
        if response is None:
            self._login_error = f"Login API not reachable: {url}"
            return False
        if response.status_code >= 400:
            self._login_error = f"Login API returned {response.status_code} (wrong e-mail/password?)"
            return False
        try:
            data = response.json()
        except ValueError:
            self._login_error = "Login API did not return JSON"
            return False
        token = self._dig(data, self.creds.token_json_path)
        if token:
            self.session.headers[self.creds.token_header] = f"{self.creds.token_prefix}{token}"
            self.auth_token_value = str(token)
        return self._verify_login(response)

    # ---- token / basic --------------------------------------------------
    def _login_token(self) -> bool:
        token = self.creds.auth_token or self.auth_token_value
        if not token:
            self._login_error = "auth_token is empty (POINTER: API token)"
            return False
        self.auth_token_value = token
        self.session.headers[self.creds.token_header] = f"{self.creds.token_prefix}{token}"
        return True

    def _login_basic(self) -> bool:
        self.session.auth = (self.creds.login_email, self.creds.login_password)
        response = self.get(self.creds.success_url or self.creds.list_url or self.base_url)
        return self._verify_login(response)

    # ---- verification ---------------------------------------------------
    @staticmethod
    def _dig(data, dotted_path: str):
        """Fetch data['a']['b'] / data['a'][0]['b'] using 'a.b' or 'a.0.b'."""
        if not dotted_path:
            return None
        current = data
        for part in str(dotted_path).split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    def _verify_login(self, response) -> bool:
        """Decide whether a login response means we are in."""
        if response is None:
            self._login_error = "No response from the login page"
            return False
        if response.status_code in (401, 403):
            self._login_error = f"Login rejected ({response.status_code}) - wrong e-mail or password"
            return False

        text = (getattr(response, "text", "") or "")
        lowered = text.lower()
        for marker in self.creds.failure_markers or []:
            if marker and marker.lower() in lowered and "logout" not in lowered:
                # "error" alone is too generic - only trust it when there is no
                # clear success signal on the page.
                if marker.lower() == "error" and self.creds.success_marker:
                    continue
                if self._has_success_marker(text):
                    continue
                self._login_error = (
                    f"The site rejected the login - its page said '{marker}'. "
                    f"Check the e-mail / password, and that TENDER_LOGIN_URL points at "
                    f"{self.login_url}"
                )
                return False

        if self.creds.success_marker:
            if self._has_success_marker(text):
                return True
            if self.creds.success_url:
                probe = self.get(self.creds.success_url)
                if probe is not None and self._has_success_marker(probe.text or ""):
                    return True
                self._login_error = (
                    f"Logged in but '{self.creds.success_marker}' not found on "
                    f"{self.creds.success_url or 'the page'} - the session may not be valid"
                )
                return False

        # Default heuristic: we were redirected away from the login page, or the
        # site gave us a session cookie, or we got a token back.
        if getattr(self, "auth_token_value", None):
            return True
        final_url = str(getattr(response, "url", "") or "")
        if final_url and self.login_url and final_url.rstrip("/") != self.login_url.rstrip("/"):
            return True
        if self.session.cookies:
            return True
        self._login_error = "Login did not redirect and set no cookies - check the login page link"
        return False

    def _has_success_marker(self, text: str) -> bool:
        marker = (self.creds.success_marker or "").strip()
        return bool(marker) and marker.lower() in (text or "").lower()

    def _verify_session(self) -> bool:
        """Are the saved cookies still good?"""
        probe_url = self.creds.success_url or self.creds.list_url or self.base_url
        if not probe_url:
            return False
        probe_url = self._page_url(self.creds.start_page) if "{page}" in probe_url else probe_url
        response = self.get(probe_url)
        if response is None:
            return False
        if self.creds.success_marker:
            return self._has_success_marker(response.text or "")
        return response.status_code == 200 and self._not_a_login_page(response)

    def _not_a_login_page(self, response) -> bool:
        final_url = str(getattr(response, "url", "") or "")
        if self.login_url and final_url.rstrip("/") == self.login_url.rstrip("/"):
            return False
        lowered = (getattr(response, "text", "") or "").lower()
        return 'type="password"' not in lowered

    def ensure_logged_in(self):
        if not self.logged_in:
            self.login()

    # ---- cookie persistence --------------------------------------------
    def _cookies_file(self) -> Optional[Path]:
        if not self.creds.save_cookies:
            return self.creds.cookies_file
        if self.creds.cookies_file:
            return Path(self.creds.cookies_file)
        return Path(config.SESSION_DIR) / f"{self.site_id}.json"

    def _save_cookies(self):
        path = self._cookies_path
        if not path:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            jar = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
                   for c in self.session.cookies]
            path.write_text(json.dumps(jar, indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"    ⚠️  Could not save session cookies: {exc}")

    def _load_cookies(self) -> bool:
        path = self._cookies_path
        if not path or not Path(path).exists():
            return False
        try:
            jar = json.loads(Path(path).read_text(encoding="utf-8"))
            for cookie in jar:
                self.session.cookies.set(
                    cookie["name"], cookie["value"],
                    domain=cookie.get("domain"), path=cookie.get("path") or "/",
                )
            return bool(jar)
        except (OSError, ValueError, KeyError):
            return False

    def logout(self):
        """Drop the saved session (e.g. after changing the password)."""
        self.session.cookies.clear()
        self.logged_in = False
        path = self._cookies_path
        if path and Path(path).exists():
            try:
                Path(path).unlink()
            except OSError:
                pass

    # ==================================================================
    # PAGES + ROWS
    # ==================================================================
    def _page_url(self, page: int) -> str:
        template = self.creds.list_url or self.creds.site_url
        if "{page}" in template:
            return template.format(page=page)
        if self.creds.page_param:
            parts = urlparse(template)
            query = parse_qs(parts.query, keep_blank_values=True)
            query[self.creds.page_param] = [str(page)]
            return urlunparse(parts._replace(query=urlencode(query, doseq=True)))
        return template

    def _has_pagination(self) -> bool:
        return bool("{page}" in (self.creds.list_url or "") or self.creds.page_param)

    def scrape(self) -> List[Dict]:
        """Login, walk every list page and return tender dicts for the database."""
        if not self.creds.is_complete:
            raise LoginError(
                "Pointers are not filled in yet. Missing: " + ", ".join(self.creds.missing) +
                "\n  -> edit credentials.py (or the .env file)"
            )
        self.ensure_logged_in()

        if self.creds.json_list_url or self.creds.json_list_path:
            tenders = self.scrape_json_api()
        else:
            tenders = self.scrape_html()

        self.tenders_found = len(tenders)
        print(f"[{self.site_name}] Scraped {len(tenders)} tenders (logged-in data)")
        return tenders

    # ---- HTML sites -----------------------------------------------------
    def scrape_html(self) -> List[Dict]:
        tenders: List[Dict] = []
        seen_urls = set()
        max_pages = self.creds.max_pages or config.MAX_PAGES_PER_SITE or 100000
        page = int(self.creds.start_page or 1)

        while page <= max_pages:
            url = self._page_url(page)
            soup = self.get_soup(url)
            if soup is None:
                # Session may have expired mid-run: log in again and retry once.
                if self.login_attempts < 2:
                    print("    🔁 Session expired? Logging in again...")
                    try:
                        self.login(force=True)
                        soup = self.get_soup(url)
                    except LoginError as exc:
                        print(f"    ❌ Re-login failed: {exc}")
                        break
                if soup is None:
                    break

            if self._looks_like_login_page(soup):
                print("    🔁 Redirected to the login page - logging in again")
                try:
                    self.login(force=True)
                    soup = self.get_soup(url)
                except LoginError as exc:
                    print(f"    ❌ Re-login failed: {exc}")
                    break
                if soup is None or self._looks_like_login_page(soup):
                    break

            rows = self._find_rows(soup)
            if not rows:
                break

            page_titles = []
            added = 0
            for row in rows:
                tender = self._parse_row(row, url)
                if not tender:
                    continue
                if tender["source_url"] in seen_urls:
                    continue
                seen_urls.add(tender["source_url"])
                page_titles.append(tender["title"])
                if self.creds.fetch_details:
                    tender = self._enrich_with_details(tender) or tender
                tenders.append(tender)
                added += 1

            if added == 0:
                break
            if page_titles and page_titles == self._seen_titles:
                break  # same page served twice -> stop
            self._seen_titles = page_titles

            if not self._has_pagination():
                break
            page += 1

        return tenders

    def _looks_like_login_page(self, soup: BeautifulSoup) -> bool:
        return soup.find("input", {"type": "password"}) is not None

    def _find_rows(self, soup: BeautifulSoup) -> List[Tag]:
        """Tender rows for one page: CSS selector first, smart detection second."""
        if self.creds.row_selector:
            rows = soup.select(self.creds.row_selector)
            if rows:
                return rows
            print(f"    ⚠️  row_selector '{self.creds.row_selector}' matched nothing - auto-detecting")

        anchors = []
        for anchor in soup.find_all("a", href=True):
            text = anchor.get_text(" ", strip=True)
            if self._looks_like_tender(text, anchor["href"]):
                anchors.append(anchor)
        return anchors

    @staticmethod
    def _looks_like_tender(text: str, href: str = "") -> bool:
        combined = f"{text} {href}".lower()
        if len(text.strip()) < MIN_TITLE_LENGTH or len(text.strip()) > MAX_TITLE_LENGTH:
            return False
        if any(skip in combined for skip in EXCLUDE_KEYWORDS):
            return False
        return any(word in combined for word in REQUIRED_KEYWORDS)

    def _parse_row(self, row: Tag, page_url: str) -> Optional[Dict]:
        creds = self.creds
        if row.name == "a":
            link_tag = row
            container = row.parent if row.parent and row.parent.name not in ("html", "body", "[document]") else row
        else:
            link_tag = None
            if creds.link_selector:
                link_tag = row.select_one(creds.link_selector)
            if link_tag is None:
                link_tag = row.find("a", href=True)
            container = row

        title = self._select_text(container, creds.title_selector)
        if not title and link_tag is not None:
            title = link_tag.get_text(" ", strip=True)
        if not title:
            return None
        title = re.sub(r"\s+", " ", title).strip()[:MAX_TITLE_LENGTH]
        if len(title) < 8:
            return None

        href = (link_tag.get("href") if link_tag is not None else "") or ""
        source_url = urljoin(page_url, href) if href else page_url

        row_text = container.get_text(" ", strip=True) if hasattr(container, "get_text") else title

        published = self._select_text(container, creds.published_selector)
        published = self.parse_date(published) if published else None
        if not published:
            published = self.extract_date_from_text(row_text, PUBLISHED_PATTERNS)

        closing = self._select_text(container, creds.closing_selector)
        closing = self.parse_date(closing) if closing else None
        if not closing:
            closing = self.extract_date_from_text(row_text, CLOSING_PATTERNS)

        organization = self._select_text(container, creds.organization_selector)
        location = self._select_text(container, creds.location_selector)
        description = self._select_text(container, creds.description_selector)

        return self._build_tender(
            title=title,
            source_url=source_url,
            published_date=published,
            closing_date=closing,
            organization=organization,
            location=location,
            description=description,
            source_text=row_text,
        )

    def _select_text(self, container, selector: str, attr: str = None) -> Optional[str]:
        if not selector or container is None:
            return None
        try:
            element = container.select_one(selector)
        except NotImplementedError:
            print(f"    ⚠️  Selector not supported by the HTML parser: {selector}")
            return None
        if element is None:
            return None
        value = element.get(attr) if attr else element.get_text(" ", strip=True)
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        return value or None

    # ---- detail pages ---------------------------------------------------
    def _enrich_with_details(self, tender: Dict) -> Optional[Dict]:
        url = tender.get("source_url")
        if not url or url == self.base_url:
            return tender
        soup = self.get_soup(url)
        if soup is None:
            return tender
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = re.sub(r"[ \t]+", " ", main.get_text(" ", strip=True))

        details = self.extract_details(soup, text)
        merged = dict(tender)
        for key, value in details.items():
            if value and not merged.get(key):
                merged[key] = value
        merged["document_links"] = sorted(set(
            (tender.get("document_links") or []) + (details.get("document_links") or [])
        ))
        merged["source_text"] = (merged.get("source_text") or "") + " " + text
        merged["description"] = merged.get("description") or details.get("description")
        if not merged.get("category") or merged.get("category") == "other":
            merged["category"] = self.categorize(text)
        merged["status"] = self._status_for(merged.get("closing_date"))
        if config.DOWNLOAD_DOCUMENTS:
            self.download_documents(merged)
        return merged

    def extract_details(self, soup: BeautifulSoup, text: str) -> Dict:
        """Pull every useful field out of one notice page."""
        details: Dict = {}
        email_match = re.search(EMAIL_PATTERN, text or "")
        if email_match:
            details["contact_email"] = email_match.group(0)
        phone_match = re.search(PHONE_PATTERN, text or "")
        if phone_match:
            details["contact_phone"] = phone_match.group(0)

        published = self.extract_date_from_text(text, PUBLISHED_PATTERNS)
        if published:
            details["published_date"] = published
        closing = self.extract_date_from_text(text, CLOSING_PATTERNS)
        if closing:
            details["closing_date"] = closing
        pre_bid = self.extract_date_from_text(
            text, [p for p, kind in DATE_PATTERNS if kind == "pre_bid"]
        )
        if pre_bid:
            details["pre_bid_meeting"] = pre_bid

        lowered = (text or "").lower()
        for pattern in MONEY_PATTERNS:
            match = re.search(pattern, lowered)
            if match:
                value = match.group(1).strip()
                if "bond" in pattern or "security" in pattern:
                    details["bid_bond"] = value
                elif "fee" in pattern:
                    details["document_fee"] = value
                else:
                    details.setdefault("estimated_value", value)

        for label, key in (
            ("eligibility", "eligibility"),
            ("bid bond", "bid_bond"),
            ("document fee", "document_fee"),
            ("pre-bid meeting", "pre_bid_meeting"),
        ):
            if not details.get(key):
                snippet = self._labelled_text(text, label)
                if snippet:
                    details[key] = snippet

        details["description"] = (text or "")[:4000] or None
        details["document_links"] = self._document_links(soup, str(getattr(soup, "url", "") or self.base_url))
        return details

    @staticmethod
    def _labelled_text(text: str, label: str, limit: int = 300) -> Optional[str]:
        pattern = re.compile(re.escape(label) + r"\s*[:\-]?\s*(.{5,%d})" % limit, re.I)
        match = pattern.search(text or "")
        return match.group(1).strip() if match else None

    @staticmethod
    def _document_links(soup: BeautifulSoup, page_url: str) -> List[str]:
        links: List[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            lowered = href.lower()
            if lowered.endswith(DOCUMENT_EXTENSIONS) or "download" in lowered or "attachment" in lowered:
                links.append(urljoin(page_url, href))
        return sorted(set(links))

    def download_documents(self, tender: Dict):
        """Save tender documents to data/documents/<site>/ and record a manifest."""
        folder = Path(config.DOWNLOAD_DIR) / self.site_id
        manifest_path = folder / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        except (OSError, ValueError):
            manifest = {}

        for link in tender.get("document_links") or []:
            if link in manifest:
                continue
            try:
                response = self.get(link, stream=True)
                if response is None or response.status_code != 200:
                    continue
                name = Path(urlparse(link).path).name or hashlib.md5(link.encode()).hexdigest()[:10]
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
                with open(target, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=65536):
                        handle.write(chunk)
                manifest[link] = str(target)
            except OSError as exc:
                print(f"    ⚠️  Could not download {link}: {exc}")

        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ---- JSON API sites -------------------------------------------------
    def scrape_json_api(self) -> List[Dict]:
        tenders: List[Dict] = []
        seen = set()
        max_pages = self.creds.max_pages or config.MAX_PAGES_PER_SITE or 100000
        page = int(self.creds.start_page or 1)
        base = self.creds.json_list_url or self.creds.list_url or self.creds.site_url

        while page <= max_pages:
            url = base.format(page=page) if "{page}" in base else base
            if "{page}" not in base and self.creds.page_param:
                parts = urlparse(url)
                query = parse_qs(parts.query, keep_blank_values=True)
                query[self.creds.page_param] = [str(page)]
                url = urlunparse(parts._replace(query=urlencode(query, doseq=True)))

            payload = self.get_json(url)
            if not payload:
                break
            items = self._dig(payload, self.creds.json_list_path) or []
            if isinstance(items, dict):
                items = items.get("data") or items.get("items") or items.get("tenders") or []
            if not isinstance(items, list) or not items:
                break

            added = 0
            for item in items:
                tender = self._parse_json_item(item, base)
                if not tender or tender["source_url"] in seen:
                    continue
                seen.add(tender["source_url"])
                tenders.append(tender)
                added += 1
            if added == 0 or "{page}" not in base and not self.creds.page_param:
                break
            page += 1

        return tenders

    def _parse_json_item(self, item: Dict, base_url: str) -> Optional[Dict]:
        if not isinstance(item, dict):
            return None
        mapping = self.creds.json_item_map or {}

        def pick(*keys):
            for key in keys:
                if key and item.get(key) not in (None, ""):
                    return item[key]
            return None

        title = pick(mapping.get("title"), "title", "notice_title", "tender_title", "name", "subject")
        if not title:
            return None
        title = re.sub(r"\s+", " ", str(title)).strip()[:MAX_TITLE_LENGTH]

        link = pick(mapping.get("source_url"), "url", "link", "slug")
        if link:
            source_url = link if str(link).startswith("http") else urljoin(self.base_url.rstrip("/") + "/", str(link).lstrip("/"))
        else:
            identifier = pick("id", "tender_code", "code", "reference_no")
            source_url = f"{self.base_url.rstrip('/')}/tender/{identifier or hashlib.md5(title.encode()).hexdigest()[:10]}"

        published = self.pick_date(item, [mapping.get("published_date"), "published_date", "publishedDate", "created_at", "date"])
        closing = self.pick_date(item, [mapping.get("closing_date"), "closing_date", "closingDate", "due_date", "deadline", "end_date"])
        docs = item.get(mapping.get("document_links") or "documents") or item.get("document") or []
        if isinstance(docs, str):
            docs = [docs]
        document_links = []
        for doc in docs if isinstance(docs, list) else []:
            if isinstance(doc, str):
                document_links.append(doc)
            elif isinstance(doc, dict):
                value = doc.get("url") or doc.get("file") or doc.get("path")
                if value:
                    document_links.append(value)

        return self._build_tender(
            title=title,
            source_url=source_url,
            published_date=published,
            closing_date=closing,
            organization=pick(mapping.get("organization"), "organization", "organisation", "ministry", "authority"),
            location=pick(mapping.get("location"), "location", "district", "province"),
            description=item.get(mapping.get("description") or "description"),
            source_text=f"{title} {item.get('category', '')}",
            document_links=document_links,
            extra={
                "category": pick(mapping.get("category"), "category", "category_name"),
                "estimated_value": pick("estimated_value", "value", "budget"),
                "contact_person": pick("contact_person", "contact"),
                "contact_email": pick("contact_email", "email"),
                "contact_phone": pick("contact_phone", "phone"),
            },
        )

    # ==================================================================
    # Shared shaping for the database
    # ==================================================================
    def _build_tender(self, title: str, source_url: str, published_date: Optional[str] = None,
                      closing_date: Optional[str] = None, organization: Optional[str] = None,
                      location: Optional[str] = None, description: Optional[str] = None,
                      source_text: str = "", document_links: Optional[List[str]] = None,
                      extra: Optional[Dict] = None) -> Dict:
        extra = extra or {}
        category = extra.get("category") or self.categorize(f"{title} {source_text}")
        identifier = extra.get("source_id") or hashlib.md5(source_url.encode()).hexdigest()[:12]
        tender = {
            "source_site_id": self.site_id,
            "source_id": f"{self.site_id}_{identifier}",
            "title": title,
            "organization": organization or self.site_name,
            "published_date": published_date,
            "closing_date": closing_date,
            "location": location or "Sri Lanka",
            "category": category,
            "estimated_value": extra.get("estimated_value"),
            "currency": extra.get("currency") or "LKR",
            "description": (description or source_text or "")[:4000] or None,
            "eligibility": extra.get("eligibility"),
            "bid_bond": extra.get("bid_bond"),
            "contact_person": extra.get("contact_person"),
            "contact_email": extra.get("contact_email"),
            "contact_phone": extra.get("contact_phone"),
            "collection_address": extra.get("collection_address"),
            "submission_address": extra.get("submission_address"),
            "document_fee": extra.get("document_fee"),
            "pre_bid_meeting": extra.get("pre_bid_meeting"),
            "document_links": document_links or [],
            "source_url": source_url,
            "status": self._status_for(closing_date),
            "source_name": self.site_name,
        }
        return tender

    @staticmethod
    def _status_for(closing_date: Optional[str]) -> str:
        """Closed notices are kept (never deleted) but marked as closed."""
        if not closing_date:
            return "open"
        try:
            closing = date.fromisoformat(str(closing_date)[:10])
        except ValueError:
            return "open"
        return "closed" if closing < date.today() else "open"

    @staticmethod
    def categorize(text: str) -> str:
        """Same keyword rules as GenericScraper so categories match across sites."""
        return categorize_text(text)
