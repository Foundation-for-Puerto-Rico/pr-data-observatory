"""Local test tool for the capture scripts (plan item 6 regression harness; see README.md).

    python tests/browser/collector.py [CAPTURES_DIR]      # listens on 127.0.0.1:8099 (PORT overrides); CAPTURES_DIR defaults to cache/captures

POST /save?name=X writes X.json to CAPTURES_DIR; GET /s/NAME serves the capture script tests/browser/NAME. CORS is open and the server listens on localhost only.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[1] / "cache" / "captures"
OUT.mkdir(parents=True, exist_ok=True)


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, code, body=b"", ctype=None):
        self.send_response(code)
        self._cors()
        if ctype:
            self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/s/"):
            f = HERE / "".join(c for c in path[3:] if c.isalnum() or c in "-_.")
            if f.is_file() and f.suffix in (".js", ".json"):
                return self._send(200, f.read_bytes(), "text/javascript; charset=utf-8" if f.suffix == ".js" else "application/json")
            return self._send(404)
        self._send(200, b"collector ready")

    def do_POST(self):
        q = parse_qs(urlparse(self.path).query)
        name = "".join(c for c in (q.get("name") or ["x"])[0] if c.isalnum() or c in "-_.")
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        (OUT / f"{name}.json").write_bytes(body)
        self._send(200, json.dumps({"saved": name, "bytes": n}).encode(), "application/json")

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8099"))), H).serve_forever()
