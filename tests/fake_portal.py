"""
A tiny fake "login-protected tender portal" used by the tests and by manual
smoke runs. Not part of the product - it only exists so the login/scraper code
can be exercised without touching a real (paid, private) tender website.

Routes:
    GET  /login              HTML login form with a CSRF hidden field
    POST /login              validates e-mail + password + CSRF, sets a cookie
    GET  /tenders?page=N     tender list (protected), 2 rows per page
    GET  /tender/<id>        notice detail page (dates, contacts, PDF)
    POST /api/login          JSON login -> {"data": {"access_token": ...}}
    GET  /api/tenders        JSON tender list (Bearer token protected)

Run it standalone:  python -m tests.fake_portal 8765
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

EMAIL = "buyer@example.lk"
PASSWORD = "S3cret-pass"
API_TOKEN = "tok-abc-123"
LOGIN_COUNT = {"form": 0, "json": 0}

TENDERS = [
    ("1", "Tender for the Supply of Office Equipment - Ministry of Health", "05/01/2027", "10/12/2026"),
    ("2", "Quotation for Construction of a New Water Treatment Plant", "15/03/2026", "01/12/2026"),
    ("3", "Procurement of Medical Consumables for Teaching Hospital", "20/11/2025", "02/11/2025"),
]


class FakeTenderPortal(BaseHTTPRequestHandler):
    """Login-protected tender site: /login, /tenders?page=N, /tender/<id>, /api/*"""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep test output clean
        pass

    # ---- helpers -------------------------------------------------------
    def _send(self, body: str, status: int = 200, headers=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload, status: int = 200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @property
    def _cookie(self):
        return self.headers.get("Cookie", "")

    def _logged_in(self):
        return "sid=valid" in self._cookie

    def _bearer_ok(self):
        return self.headers.get("Authorization") == f"Bearer {API_TOKEN}"

    # ---- routes --------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)

        if path == "/login":
            return self._send(
                "<html><body><form method='post' action='/login'>"
                "<input type='hidden' name='_token' value='csrf-xyz'>"
                "<input type='email' name='email'>"
                "<input type='password' name='password'>"
                "<button type='submit'>Sign in</button></form></body></html>"
            )

        if path == "/tenders":
            if not self._logged_in():
                return self._send("", status=302, headers={"Location": "/login"})
            page = int((query.get("page") or ["1"])[0])
            rows = TENDERS[(page - 1) * 2: page * 2]  # 2 per page -> 3 pages, last empty
            body = "".join(
                f"<li class='tender-row'><a href='/tender/{tid}'>{title}</a>"
                f"<span class='meta'>Closing Date: {closing} | Published on: {published}</span></li>"
                for tid, title, closing, published in rows
            )
            return self._send(
                "<html><body><a href='/logout'>Logout</a>"
                f"<ul class='tender-list'>{body}</ul></body></html>"
            )

        if path.startswith("/tender/"):
            if not self._logged_in():
                return self._send("", status=302, headers={"Location": "/login"})
            tid = path.rsplit("/", 1)[-1]
            info = next((t for t in TENDERS if t[0] == tid), TENDERS[0])
            return self._send(
                "<html><body><main>"
                f"<h1>{info[1]}</h1>"
                f"<p>Invitation for bids. Closing Date: {info[2]} at 10:00.</p>"
                "<p>Contact email: procurement@health.gov.lk - Contact 0712345678</p>"
                "<p>Bid Bond: LKR 500,000</p>"
                "<a href='/files/notice.pdf'>Notice document</a>"
                "</main></body></html>"
            )

        if path == "/api/tenders":
            if not self._bearer_ok():
                return self._json({"message": "unauthenticated"}, status=401)
            page = int((query.get("page") or ["1"])[0])
            items = [
                {
                    "id": tid, "title": title, "closing_date": closing,
                    "published_date": published, "organization": "Test Authority",
                    "category": "goods", "documents": [f"/files/{tid}.pdf"],
                }
                for tid, title, closing, published in TENDERS[(page - 1) * 2: page * 2]
            ]
            return self._json({"data": items, "page": page})

        return self._send("<html><body>404</body></html>", status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")

        if parsed.path == "/login":
            form = {k: v[0] for k, v in parse_qs(raw).items()}
            LOGIN_COUNT["form"] += 1
            ok = (
                form.get("email") == EMAIL
                and form.get("password") == PASSWORD
                and form.get("_token") == "csrf-xyz"  # CSRF token must be carried over
            )
            if ok:
                return self._send(
                    "<html><body>Logout</body></html>",
                    status=200,
                    headers={"Set-Cookie": "sid=valid; Path=/"},
                )
            return self._send("<html><body>Invalid credentials, try again</body></html>")

        if parsed.path == "/api/login":
            LOGIN_COUNT["json"] += 1
            try:
                payload = json.loads(raw)
            except ValueError:
                return self._json({"message": "bad json"}, status=400)
            if payload.get("email") == EMAIL and payload.get("password") == PASSWORD:
                return self._json({"data": {"access_token": API_TOKEN}})
            return self._json({"message": "unauthorised"}, status=401)

        return self._send("", status=404)


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeTenderPortal)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"




def start_server():
    """Start the fake portal on a free port; returns (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeTenderPortal)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    httpd = ThreadingHTTPServer(("0.0.0.0", port), FakeTenderPortal)
    httpd.daemon_threads = True
    print(f"fake tender portal listening on 0.0.0.0:{port} "
          f"(email={EMAIL} password={PASSWORD})", flush=True)
    httpd.serve_forever()
