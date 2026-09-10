"""
End-to-end tests for the login-protected scraper base.

These do NOT hit the internet: a tiny local HTTP server pretends to be a
private tender portal (HTML form login + CSRF token + paginated list + notice
detail pages, plus a JSON-API variant). The tests then run the real
AuthenticatedScraper code against it and check the data that comes out, and
that it can be written to the tender database.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TMP_DIR = Path(tempfile.mkdtemp(prefix="tender_auth_test_"))
# Point the project at throw-away paths BEFORE importing config/database.
os.environ["TENDER_DB_PATH"] = str(TMP_DIR / "test.db")
os.environ["TENDER_SESSION_DIR"] = str(TMP_DIR / "sessions")
os.environ["TENDER_DEBUG_DIR"] = str(TMP_DIR / "debug")
os.environ["TENDER_ENV_FILE"] = str(TMP_DIR / "missing.env")  # ignore any real .env
for key in list(os.environ):
    if key.startswith("TENDER_") and key not in (
        "TENDER_DB_PATH", "TENDER_SESSION_DIR", "TENDER_DEBUG_DIR", "TENDER_ENV_FILE"
    ):
        del os.environ[key]

import config  # noqa: E402
import database  # noqa: E402
from credentials import SiteCredentials  # noqa: E402
from scrapers.auth_base import AuthenticatedScraper, LoginError  # noqa: E402

from tests.fake_portal import (  # noqa: E402
    EMAIL, LOGIN_COUNT, PASSWORD, TENDERS, API_TOKEN, start_server,
)


def html_credentials(base_url: str, **overrides) -> SiteCredentials:
    creds = SiteCredentials(
        site_url=base_url,
        login_email=EMAIL,
        login_password=PASSWORD,
        login_url=f"{base_url}/login",
        list_url=f"{base_url}/tenders?page={{page}}",
        success_marker="logout",
        site_id="test_portal",
        site_name="Test Portal",
        polite_delay=0.0,
    )
    for key, value in overrides.items():
        setattr(creds, key, value)
    return creds


class AuthScraperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base_url = start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def make_scraper(self, **overrides) -> AuthenticatedScraper:
        return AuthenticatedScraper(html_credentials(self.base_url, **overrides))

    # ------------------------------------------------------------------
    def test_form_login_carries_csrf_token_and_sets_session(self):
        LOGIN_COUNT["form"] = 0
        scraper = self.make_scraper(cookies_file=TMP_DIR / "cookies_form.json")
        self.assertTrue(scraper.login())
        self.assertTrue(scraper.logged_in)
        self.assertEqual(LOGIN_COUNT["form"], 1)
        # the CSRF hidden field was sent, otherwise the server rejects the login
        self.assertEqual(scraper.session.cookies.get("sid"), "valid")
        self.assertTrue((TMP_DIR / "cookies_form.json").exists())

    def test_wrong_password_raises_login_error(self):
        scraper = self.make_scraper(
            login_password="not-the-password",
            cookies_file=TMP_DIR / "cookies_bad.json",
        )
        with self.assertRaises(LoginError) as ctx:
            scraper.login()
        self.assertIn("site rejected the login", str(ctx.exception))
        self.assertIn("'invalid'", str(ctx.exception))

    def test_saved_session_is_reused_without_logging_in_again(self):
        cookies = TMP_DIR / "cookies_reuse.json"
        first = self.make_scraper(cookies_file=cookies)
        first.login()
        LOGIN_COUNT["form"] = 0
        second = self.make_scraper(cookies_file=cookies)
        self.assertTrue(second.login())
        self.assertEqual(LOGIN_COUNT["form"], 0, "saved session should avoid a new login")

    def test_scrape_walks_pagination_and_extracts_full_details(self):
        scraper = self.make_scraper(cookies_file=TMP_DIR / "cookies_scrape.json")
        tenders = scraper.scrape()

        self.assertEqual(len(tenders), len(TENDERS))
        self.assertEqual(scraper.tenders_found, len(TENDERS))

        by_title = {t["title"]: t for t in tenders}
        first = by_title[TENDERS[0][1]]
        self.assertEqual(first["source_site_id"], "test_portal")
        self.assertEqual(first["source_url"], f"{self.base_url}/tender/1")
        self.assertEqual(first["closing_date"], "2027-01-05")     # 05/01/2027, day-first
        self.assertEqual(first["published_date"], "2026-12-10")  # 10/12/2026
        self.assertEqual(first["status"], "open")
        # "Ministry of Health" wins over "Supply" - health is checked before
        # goods by the shared rule set, exactly like GenericScraper does.
        self.assertEqual(first["category"], "health")
        # detail page fields
        self.assertEqual(first["contact_email"], "procurement@health.gov.lk")
        self.assertIn("500,000", first["bid_bond"] or "")
        self.assertIn(f"{self.base_url}/files/notice.pdf", first["document_links"])

        # the closed one is kept, not dropped, and marked closed
        old = by_title[TENDERS[2][1]]
        self.assertEqual(old["closing_date"], "2025-11-20")
        self.assertEqual(old["status"], "closed")

    def test_scraped_tenders_are_saved_to_the_database(self):
        scraper = self.make_scraper(cookies_file=TMP_DIR / "cookies_db.json")
        tenders = scraper.scrape()
        database.init_db()
        saved = [t for t in tenders if database.insert_tender(t, is_primary=1)]
        self.assertTrue(saved, "expected new rows to be inserted")

        import sqlite3
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT title, closing_date, contact_email, status FROM tenders "
            "WHERE source_site_id = 'test_portal'"
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), len(TENDERS))
        self.assertIn("2027-01-05", [r["closing_date"] for r in rows])
        self.assertIn("procurement@health.gov.lk", [r["contact_email"] for r in rows])

    def test_json_api_login_and_list(self):
        creds = html_credentials(
            self.base_url,
            auth_method="json",
            login_api_url=f"{self.base_url}/api/login",
            login_url=f"{self.base_url}/api/login",
            token_json_path="data.access_token",
            json_list_url=f"{self.base_url}/api/tenders?page={{page}}",
            json_list_path="data",
            cookies_file=TMP_DIR / "cookies_json.json",
        )
        scraper = AuthenticatedScraper(creds)
        tenders = scraper.scrape()
        self.assertEqual(len(tenders), len(TENDERS))
        self.assertEqual(scraper.session.headers["Authorization"], f"Bearer {API_TOKEN}")
        self.assertEqual(tenders[0]["closing_date"], "2027-01-05")
        self.assertEqual(tenders[0]["organization"], "Test Authority")
        self.assertIn("/files/1.pdf", tenders[0]["document_links"])

    def test_bad_json_credentials_are_reported(self):
        creds = html_credentials(
            self.base_url,
            auth_method="json",
            login_api_url=f"{self.base_url}/api/login",
            login_url=f"{self.base_url}/api/login",
            login_password="wrong",
            cookies_file=TMP_DIR / "cookies_json_bad.json",
        )
        with self.assertRaises(LoginError):
            AuthenticatedScraper(creds).login()

    def test_missing_pointers_are_reported_clearly(self):
        blank = SiteCredentials(site_url="", login_email="", login_password="")
        self.assertFalse(blank.is_complete)
        self.assertEqual(len(blank.missing), 3)
        self.assertIn("POINTER 1", blank.missing[0])
        with self.assertRaises(LoginError) as ctx:
            AuthenticatedScraper(blank).scrape()
        self.assertIn("credentials.py", str(ctx.exception))

    def test_placeholder_values_count_as_empty(self):
        placeholder = SiteCredentials(
            site_url="https://PUT-YOUR-TENDER-SITE-LINK-HERE",
            login_email="PUT-YOUR-LOGIN-EMAIL-HERE",
            login_password="hunter2",
        ).from_env_copy()
        self.assertEqual(placeholder.site_url, "")
        self.assertFalse(placeholder.is_complete)
        self.assertFalse(AuthenticatedScraper.credentials_ready())

    def test_category_rules(self):
        self.assertEqual(AuthenticatedScraper.categorize("Supply of Computer Servers"), "IT")
        self.assertEqual(AuthenticatedScraper.categorize("Road construction contract"), "construction")
        self.assertEqual(AuthenticatedScraper.categorize("Cleaning service for office"), "services")
        self.assertEqual(AuthenticatedScraper.categorize("Something unrelated"), "other")

    def test_categories_match_the_public_site_scraper(self):
        """The same notice must get the same category on both scraper types."""
        from scrapers.generic import GenericScraper
        generic = GenericScraper(source_id="x", name="x", base_url=self.base_url, tender_url=self.base_url)
        samples = [
            "Tender for the Supply of Office Equipment - Ministry of Health",
            "Supply of Computer Servers",
            "Road construction contract for provincial highway",
            "Cleaning service for office building",
            "Solar power plant installation",
            "Something unrelated",
        ]
        for text in samples:
            self.assertEqual(
                AuthenticatedScraper.categorize(text),
                generic.categorize(text),
                f"category mismatch for: {text}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
