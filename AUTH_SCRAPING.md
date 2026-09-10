# 🔐 Scraping a tender site that needs a LOGIN

**සිංහලෙන් (සරලව):** ඔබේ tender වෙබ් අඩවියට login එකක් (e-mail + password) තිබෙනවා නම්,
`credentials.py` (හෝ `.env` ගොනුව) තුළ **link එක, login e-mail එක, password එක** දාන්න.
ඊට පස්සේ `python check_login.py` කියලා login එක හරිද කියලා බලන්න. හරි නම්
`python run_scraper.py` කියලා දත්ත ඔක්කොම `tenders.db` එකට ගන්න.

---

## 1. Fill in the pointers (one time only)

**Option A — recommended (password stays off GitHub):**

```bash
cp .env.example .env
# open .env and fill in:
#   TENDER_SITE_URL      -> POINTER 1 : the link of the site
#   TENDER_LOGIN_EMAIL   -> POINTER 2 : login e-mail
#   TENDER_LOGIN_PASSWORD-> POINTER 3 : password
#   TENDER_LOGIN_URL     -> POINTER 4 : login page (optional)
```

**Option B — type them straight into the code:** edit `credentials.py`, the block
marked `👉👉👉 EDIT BELOW THIS LINE`.

`.env` values always win over the values typed in `credentials.py`.
Check what the automation will use (password hidden):

```bash
python credentials.py
```

## 2. Test the login

```bash
python check_login.py            # log in and show the first 10 tenders
python check_login.py --save     # also save the pages into data/debug/
python check_login.py --pages 3  # walk 3 list pages
```

What it tells you:

| Message | Meaning |
|---|---|
| `❌ Not ready. These pointers are still empty` | fill in `credentials.py` / `.env` |
| `❌ Login FAILED` | wrong e-mail/password, or wrong login page link |
| `✅ Login OK` + `⚠️ no tender rows found` | set `TENDER_LIST_URL` / `TENDER_ROW_SELECTOR` |
| `✅ Found N tenders` | done — go to step 3 |

## 3. Collect the data

```bash
python -m scrapers.my_tender_site   # this site only
python run_scraper.py               # all sites (private site included)
```

Everything lands in `tenders.db` (table `tenders`) with the same columns the
rest of the hub uses: title, organization, published/closing date, location,
category, description, contact e-mail/phone, bid bond, document fee,
document links, source url, status.

Saved logins are cached in `.sessions/` so the site is not hit with a login on
every run. After changing the password: `python -m credentials` or delete
`.sessions/my_tender_site.json`.

---

## How the automation works

```
credentials.py   ->  the 4 pointers (link, login page, e-mail, password)
      |
scrapers/auth_base.py  ->  AuthenticatedScraper (the "base" for login sites)
      |        login -> session cookies -> list pages -> detail pages
scrapers/my_tender_site.py  ->  your site (nothing to edit normally)
      |
database.insert_tender()  ->  tenders.db  ->  api.py / seo.py / mcp_server.py
```

`AuthenticatedScraper` handles:

* **4 login styles** — `form` (normal web login page), `json` (API login that
  returns a token), `token` (API key you already have), `basic` (HTTP basic)
* **CSRF / hidden fields** — tokens on the login form (`_token`, `csrf`, ...)
  are collected and sent back automatically
* **session reuse + auto re-login** when the session dies mid-run
* **pagination** — `{page}` in the URL or `?page=1,2,3...`, walking until the
  site returns nothing new (full history, old + new, like the other scrapers)
* **row detection** — your CSS selector if given, otherwise automatic
  detection of links that look like real tender notices
* **detail extraction** — dates, contact e-mail/phone, bid bond, document fee,
  pre-bid meeting, description, PDF/DOC download links
* **optional document download** — `DOWNLOAD_DOCUMENTS=1` saves the files into
  `data/documents/<site>/` plus a `manifest.json`

## When auto-detection is not enough

Open the tender list page in your browser, press **F12**, right-click one
tender row → *Copy → Copy selector*, and put it in `.env`:

```ini
TENDER_LIST_URL=https://your-tender-site.lk/tenders?page={page}
TENDER_ROW_SELECTOR=div.tender-card
TENDER_TITLE_SELECTOR=.title
TENDER_CLOSING_SELECTOR=.deadline
```

Or do it in code — `scrapers/my_tender_site.py`:

```python
MY_SITE.row_selector = "div.tender-card"
MY_SITE.closing_selector = ".deadline"
MY_SITE.success_marker = "logout"
```

**JSON API site?** Put the endpoint in `.env` and it switches to JSON mode:

```ini
TENDER_AUTH_METHOD=json
TENDER_LOGIN_API_URL=https://your-tender-site.lk/api/login
TENDER_TOKEN_JSON_PATH=data.access_token
TENDER_JSON_LIST_URL=https://your-tender-site.lk/api/tenders?page={page}
TENDER_JSON_LIST_PATH=data
```

## Notes

* Only scrape a site you are allowed to scrape, and keep
  `polite_delay` (default 1 s between requests) as it is.
* Passwords live in `.env` / `credentials.py` only — both are git-ignored
  (`.env`) or should be left with placeholders before committing.
* JavaScript-only sites (data rendered by React with no HTML) need a real
  browser; the current base uses `cloudscraper` + `requests` sessions.
* Tests: `python -m unittest discover -s tests -v` (runs a fake login-protected
  site locally and checks login, pagination, parsing and DB insert).
