"""Local web server for the CSIA dashboard — Python stdlib only (keeps the
dependency set lean; no flask/plotly). Serves the static single-page app
from src/dashboard/web/ and the replay JSONs from data/replay/ under /data/.
"""

import json
import logging
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
DEFAULT_REPLAY_DIR = os.path.abspath(os.path.join(os.getcwd(), "data", "replay"))
_replay_dir = DEFAULT_REPLAY_DIR
_live = None   # optional callable -> live doc dict (set by run_service)


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/data/index.json":
            names = sorted(f[:-5] for f in os.listdir(_replay_dir)
                           if f.endswith(".json"))
            if _live is not None:
                names = ["live"] + names
            self._json(names)
            return
        if self.path == "/data/live.json":
            doc = _live() if _live is not None else None
            if doc is None:
                self._json({"error": "live feed warming up"}, code=503)
            else:
                self._json(doc)
            return
        if self.path.startswith("/data/"):
            fname = os.path.basename(self.path)
            fpath = os.path.join(_replay_dir, fname)
            if os.path.isfile(fpath) and fname.endswith(".json"):
                with open(fpath, "rb") as fh:
                    body = fh.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)


def serve(port: int = 8017, replay_dir: str | None = None,
          host: str = "127.0.0.1", live=None):
    """Serve the dashboard. Binds loopback by default — this is a local
    analysis tool, not a hardened public web service. ``live`` is an
    optional callable returning the current live-feed doc (see
    runtime.service.LiveFeed)."""
    global _replay_dir, _live
    _live = live
    _replay_dir = os.path.abspath(replay_dir or DEFAULT_REPLAY_DIR)
    if not os.path.isdir(_replay_dir):
        raise FileNotFoundError(
            f"no replay directory at {_replay_dir} — run `csia build` first")
    httpd = ThreadingHTTPServer((host, port), DashboardHandler)
    log.info("CSIA dashboard: http://%s:%d (replays: %s)", host, port, _replay_dir)
    print(f"CSIA dashboard: http://{host}:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("dashboard stopped")
