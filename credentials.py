"""
============================================================================
👉 POINTER FILE — THIS IS THE FILE YOU EDIT
============================================================================
Your tender website asks for a login (e-mail + password) before it shows the
tender data. This file holds the 3 things the automation needs to know:

    👉 POINTER 1  ->  the LINK of the site          (site_url)
    👉 POINTER 2  ->  the LOGIN E-MAIL / username   (login_email)
    👉 POINTER 3  ->  the PASSWORD                  (login_password)
    👉 POINTER 4  ->  the LOGIN PAGE link (optional)(login_url)

You can fill them in TWO ways (pick one):

  (A) EASY / SAFE  - copy `.env.example` to `.env` and write your details there.
      `.env` is git-ignored, so your password is never pushed to GitHub.

  (B) DIRECT       - type the values into the MY_SITE block at the bottom of
      this file (the lines marked 👉 POINTER). Do NOT commit real passwords.

Values written in `.env` / environment variables always WIN over the values
typed in this file, so you can keep this file clean and secret-free.

Nothing else needs to change: run_scraper.py, check_login.py and the scraper
all read their settings from this file.
============================================================================
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).parent.resolve()

# ---------------------------------------------------------------------------
# Small built-in .env reader (no extra dependency needed)
# ---------------------------------------------------------------------------
ENV_FILE = Path(os.getenv("TENDER_ENV_FILE", str(BASE_DIR / ".env")))


def load_env_file(path: Path = ENV_FILE) -> Dict[str, str]:
    """Read KEY=VALUE lines from a .env file into os.environ.

    Real environment variables always win, so you can override anything at
    runtime (`TENDER_LOGIN_PASSWORD=... python run_scraper.py`).
    """
    loaded: Dict[str, str] = {}
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return loaded

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


load_env_file()


def _env(name: str, default: str = "") -> str:
    """Environment variable (or .env entry) or the default typed in this file."""
    return os.getenv(name, default) or default


# Text that means "the user has not filled this in yet" - these values are
# treated as EMPTY so the scraper reports the pointers as missing instead of
# trying to log in to "https://PUT-YOUR-TENDER-SITE-LINK-HERE".
PLACEHOLDER = re.compile(r"put[-_ ]?your|change[-_ ]?me|your-[\w-]*-here|xxxxxxxx", re.I)


def _is_placeholder(value) -> bool:
    return bool(value) and isinstance(value, str) and bool(PLACEHOLDER.search(value))


def _mask(secret: str) -> str:
    """Never print a real password - show only its length."""
    if not secret:
        return "(empty)"
    return "*" * min(len(secret), 12) + f" ({len(secret)} chars)"


# ---------------------------------------------------------------------------
# Settings for one login-protected site
# ---------------------------------------------------------------------------
@dataclass
class SiteCredentials:
    """Everything the automation needs to log in to ONE tender website.

    Only the first three fields are required. Every other field is optional
    tuning - leave it as "" / None and the scraper auto-detects your site's
    layout (login form fields, list rows, dates, document links).
    """

    # ======================= THE 3 MAIN POINTERS ============================
    site_url: str = ""          # 👉 POINTER 1: link of the site
    login_email: str = ""       # 👉 POINTER 2: login e-mail / username
    login_password: str = ""    # 👉 POINTER 3: password
    # =========================================================================

    site_id: str = "my_tender_site"     # short id used in the database
    site_name: str = "My Tender Site"   # name shown in the logs

    # 👉 POINTER 4: the login page itself. Empty = try <site_url>/login
    login_url: str = ""
    # Page you land on after a successful login (used to double-check login).
    # Empty = the scraper guesses from the redirect / cookies.
    success_url: str = ""
    # A word that is ONLY visible when you are logged in, e.g. "Logout" or
    # "Dashboard". Makes the login check 100% reliable.
    success_marker: str = ""
    # Words that mean the login FAILED (lower case match on the response).
    failure_markers: List[str] = field(default_factory=lambda: [
        "invalid", "incorrect", "wrong password", "failed", "error",
        "unauthorised", "unauthorized", "try again", "not found",
    ])

    # ---- how the site authenticates (form | json | token | basic) ----------
    auth_method: str = "form"
    # form  = normal web login page (HTML <form> with e-mail + password)
    # json  = POST {email, password} to an API, get back a token (login_api_url)
    # token = you already have an API key / bearer token (auth_token)
    # basic = HTTP basic auth (rare)
    login_api_url: str = ""       # json method: e.g. https://site.lk/api/login
    auth_token: str = ""          # token method: the API key / bearer token
    email_field: str = ""         # form method: <input name="..."> (auto-detect)
    password_field: str = ""      # form method: <input name="..."> (auto-detect)
    login_payload_extra: Dict[str, str] = field(default_factory=dict)  # extra fields
    token_json_path: str = "token"        # json method: where the token sits in the JSON
    token_header: str = "Authorization"   # header the token is sent in
    token_prefix: str = "Bearer "         # usually "Bearer " or ""

    # ---- where the tender list lives ---------------------------------------
    # Use {page} to make it paginate, e.g. https://site.lk/tenders?page={page}
    list_url: str = ""
    page_param: str = ""          # e.g. "page" -> ?page=1, ?page=2 ...
    start_page: int = 1
    max_pages: Optional[int] = None   # None = walk until the site runs out

    # ---- HTML selectors (only if auto-detection misses your layout) --------
    row_selector: str = ""        # CSS selector of ONE tender row/card
    title_selector: str = ""
    link_selector: str = ""       # CSS selector of the link inside a row
    published_selector: str = ""
    closing_selector: str = ""
    organization_selector: str = ""
    location_selector: str = ""
    description_selector: str = ""
    fetch_details: bool = True    # open every notice page to grab full details

    # ---- JSON API mode (set this when the site has a JSON endpoint) --------
    # e.g. json_list_path="data", json_item_map={"title": "notice_title"}
    json_list_url: str = ""
    json_list_path: str = ""      # e.g. "data" or "result.tenders"
    json_item_map: Dict[str, str] = field(default_factory=dict)

    # ---- behaviour ---------------------------------------------------------
    cookies_file: Optional[Path] = None   # None = auto: .sessions/<site_id>.json
    save_cookies: bool = True
    polite_delay: float = 1.0     # seconds between requests (be nice to the site)

    # ------------------------------------------------------------------
    @property
    def is_complete(self) -> bool:
        """True when we have enough information to log in."""
        if not self.site_url:
            return False
        if self.auth_method in ("form", "json", "basic"):
            return bool(self.login_email and self.login_password)
        if self.auth_method == "token":
            return bool(self.auth_token)
        return False

    @property
    def missing(self) -> List[str]:
        """Human-readable list of what is still empty (used in error messages)."""
        missing: List[str] = []
        if not self.site_url:
            missing.append("site_url  (POINTER 1: the link of the site)")
        if self.auth_method in ("form", "json", "basic"):
            if not self.login_email:
                missing.append("login_email  (POINTER 2: login e-mail)")
            if not self.login_password:
                missing.append("login_password  (POINTER 3: password)")
        elif self.auth_method == "token" and not self.auth_token:
            missing.append("auth_token")
        return missing

    def safe_summary(self) -> str:
        """Settings as text with the password hidden - safe to print in logs."""
        return (
            f"site_url       = {self.site_url or '(not set)'}\n"
            f"login_url      = {self.login_url or '(auto)'}\n"
            f"login_email    = {self.login_email or '(not set)'}\n"
            f"login_password = {_mask(self.login_password)}\n"
            f"auth_method    = {self.auth_method}\n"
            f"list_url       = {self.list_url or self.page_param or '(auto)'}"
        )

    def from_env_copy(self, prefix: str = "TENDER") -> "SiteCredentials":
        """Return a copy with any .env / environment variable overrides applied."""
        data = self.__dict__.copy()

        def apply(key: str, env_name: str, cast=None):
            value = _env(f"{prefix}_{env_name}", "")
            if value != "":
                data[key] = cast(value) if cast else value

        apply("site_url", "SITE_URL")
        apply("site_name", "SITE_NAME")
        apply("login_email", "LOGIN_EMAIL")
        apply("login_password", "LOGIN_PASSWORD")
        apply("login_url", "LOGIN_URL")
        apply("success_url", "SUCCESS_URL")
        apply("success_marker", "SUCCESS_MARKER")
        apply("auth_method", "AUTH_METHOD")
        apply("login_api_url", "LOGIN_API_URL")
        apply("auth_token", "AUTH_TOKEN")
        apply("email_field", "EMAIL_FIELD")
        apply("password_field", "PASSWORD_FIELD")
        apply("token_json_path", "TOKEN_JSON_PATH")
        apply("token_header", "TOKEN_HEADER")
        apply("token_prefix", "TOKEN_PREFIX")
        apply("list_url", "LIST_URL")
        apply("page_param", "PAGE_PARAM")
        apply("row_selector", "ROW_SELECTOR")
        apply("title_selector", "TITLE_SELECTOR")
        apply("link_selector", "LINK_SELECTOR")
        apply("closing_selector", "CLOSING_SELECTOR")
        apply("published_selector", "PUBLISHED_SELECTOR")
        apply("json_list_url", "JSON_LIST_URL")
        apply("json_list_path", "JSON_LIST_PATH")
        apply("start_page", "START_PAGE", int)
        apply("max_pages", "MAX_PAGES", int)

        # Anything still saying "PUT-YOUR-...-HERE" counts as NOT filled in, so
        # the scraper tells you which pointer is missing instead of trying to
        # log in to a fake URL.
        for key, value in list(data.items()):
            if _is_placeholder(value):
                data[key] = ""
        return SiteCredentials(**data)


# ===========================================================================
#  👉👉👉  EDIT BELOW THIS LINE  👈👈👈
#  Put your tender site link + login details here (or in the .env file).
# ===========================================================================
MY_SITE = SiteCredentials(
    # 👉 POINTER 1 — the LINK of your tender website
    site_url=_env("TENDER_SITE_URL", "https://PUT-YOUR-TENDER-SITE-LINK-HERE"),

    # 👉 POINTER 2 — the LOGIN E-MAIL (or username) of that website
    login_email=_env("TENDER_LOGIN_EMAIL", "PUT-YOUR-LOGIN-EMAIL-HERE"),

    # 👉 POINTER 3 — the PASSWORD of that website
    login_password=_env("TENDER_LOGIN_PASSWORD", ""),

    # 👉 POINTER 4 — (optional) the exact login page, e.g. https://site.lk/login
    login_url=_env("TENDER_LOGIN_URL", ""),

    # ---- identity used in the database / logs ----
    site_id="my_tender_site",
    site_name="My Tender Site (login required)",

    # ---- optional tuning (usually NOT needed) ----
    # auth_method="form",          # form | json | token | basic
    # login_api_url="",            # for auth_method="json"
    # list_url="",                 # tender list page, {page} = page number
    # page_param="page",           # list paginates with ?page=1, ?page=2 ...
    # row_selector="",             # CSS selector of one tender row
    # success_marker="logout",     # word only visible after login
)

# Apply .env / environment overrides on top of whatever is typed above.
MY_SITE = MY_SITE.from_env_copy()


def get_site_credentials(site_id: str = "my_tender_site") -> SiteCredentials:
    """Return the credentials for a site id (currently: MY_SITE)."""
    return MY_SITE


if __name__ == "__main__":
    # `python credentials.py` -> shows what the automation will use
    print("=" * 70)
    print("Tender site login pointers (password hidden)")
    print("=" * 70)
    print(MY_SITE.safe_summary())
    print("-" * 70)
    if MY_SITE.is_complete:
        print("✅ Ready - run:  python check_login.py")
    else:
        print("❌ Not ready yet. Still missing:")
        for item in MY_SITE.missing:
            print(f"     - {item}")
        print("\nCopy .env.example to .env and fill it in, or edit this file.")
