"""Phone remote control over the local network.

Serves a small web page so a phone on the same Wi-Fi can play sounds. No cloud
service and no account: the page is generated from the local sound list.

Start it from the Window menu. The default port is 8765 and the default bind is
0.0.0.0 so phones can reach it. Every request needs a random per-session token
that is part of the URL shown in the app, so another device on the same Wi-Fi
cannot control SoundPod by guessing the address.
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>SoundPod Remote</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #0f1319; color: #d7dde5;
         font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { position: sticky; top: 0; background: #0b0e13; padding: 14px 16px;
           border-bottom: 1px solid #1b222c; display: flex; gap: 10px; align-items: center; }
  header b { color: #86f5b0; font-size: 17px; }
  header span { color: #7f8c9c; font-size: 12px; margin-left: auto; }
  input { flex: 1; background: #121821; border: 1px solid #2a3543; border-radius: 8px;
          padding: 9px 12px; color: #d7dde5; font-size: 16px; margin: 12px 16px 0; width: calc(100% - 32px); }
  main { padding: 12px 12px 40px; display: grid; gap: 8px;
         grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
  button.sound { background: #1a222d; color: #e6edf5; border: 1px solid #2a3645;
                 border-radius: 12px; padding: 14px 12px; font-size: 14px; text-align: left;
                 min-height: 64px; line-height: 1.25; }
  button.sound small { display: block; color: #7f8c9c; font-size: 11px; margin-top: 6px; }
  button.sound:active { background: #1d3b2b; border-color: #2ecc71; color: #a9ffc6; }
  .stop { position: fixed; right: 14px; bottom: 16px; width: 58px; height: 58px;
          border-radius: 50%; border: 1px solid #7f2b2b; background: #2a1616;
          color: #ff9b9b; font-size: 20px; }
  .empty { color: #7f8c9c; padding: 20px 16px; }
</style>
</head>
<body>
<header><b>SoundPod</b><span id="count"></span></header>
<input id="q" placeholder="Search sounds" autocomplete="off">
<main id="list"></main>
<button class="stop" onclick="stopAll()">&#9632;</button>
<script>
const TOKEN = __SOUNDPOD_TOKEN__;
let sounds = [];
async function apiFetch(path, options = {}) {
  options.headers = Object.assign({'X-SoundPod-Token': TOKEN}, options.headers || {});
  return fetch(path, options);
}
function render() {
  const q = document.getElementById('q').value.toLowerCase();
  const list = document.getElementById('list');
  const rows = sounds.filter(s =>
    !q || s.title.toLowerCase().includes(q) || (s.category || '').toLowerCase().includes(q));
  list.innerHTML = rows.map(s => {
    const safeId = String(s.id).replace(/[^A-Za-z0-9_-]/g, '');
    return `<button class="sound" onclick="play('${safeId}')">${escapeHtml(s.title)}` +
      `<small>${escapeHtml(s.category || '')} ${s.hotkey ? '&middot; ' + escapeHtml(s.hotkey) : ''}</small></button>`;
  }).join('') || '<div class="empty">No sounds</div>';
  document.getElementById('count').textContent = rows.length + ' sounds';
}
function escapeHtml(t) {
  return String(t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
async function play(id) {
  await apiFetch('/api/play', { method: 'POST', headers: {'Content-Type': 'application/json'},
                               body: JSON.stringify({ id }) });
  if (navigator.vibrate) navigator.vibrate(18);
}
async function stopAll() { await apiFetch('/api/stop', { method: 'POST' }); }
async function load() {
  const res = await apiFetch('/api/sounds');
  sounds = await res.json();
  render();
}
document.getElementById('q').addEventListener('input', render);
load();
</script>
</body>
</html>
"""


def lan_address() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        sock.close()
        return address
    except Exception:
        return "127.0.0.1"


class RemoteServer:
    def __init__(
        self,
        sounds: Callable[[], list[dict]],
        play: Callable[[str], None],
        stop: Callable[[], None],
        port: int = 8765,
        bind: str = "0.0.0.0",
    ):
        self.port = int(port)
        self.bind = bind
        self._sounds = sounds
        self._play = play
        self._stop = stop
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.token = secrets.token_urlsafe(18)

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self.bind in ("127.0.0.1", "localhost") else lan_address()
        return f"http://{host}:{self.port}/?t={self.token}"

    def start(self) -> str:
        if self._server is not None:
            return self.url
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
                pass

            def _supplied_token(self) -> str:
                supplied = self.headers.get("X-SoundPod-Token", "")
                if not supplied:
                    query = parse_qs(urlparse(self.path).query)
                    supplied = (query.get("t") or [""])[0]
                return supplied

            def _authorized(self) -> bool:
                return secrets.compare_digest(self._supplied_token(), outer.token)

            def _forbidden(self) -> None:
                self._send(
                    HTTPStatus.FORBIDDEN,
                    b"SoundPod remote: open the link shown in the app (it contains a session key).",
                    "text/plain; charset=utf-8",
                )

            def _send(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, payload) -> None:
                self._send(
                    HTTPStatus.OK,
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8",
                )

            def do_GET(self) -> None:
                path = urlparse(self.path).path
                if path == "/favicon.ico":
                    self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
                    return
                if not self._authorized():
                    self._forbidden()
                    return
                if path in ("/", "/index.html"):
                    page = PAGE.replace(
                        "__SOUNDPOD_TOKEN__", json.dumps(outer.token)
                    )
                    self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")
                elif path == "/api/sounds":
                    self._json(outer._sounds())
                else:
                    self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

            def do_POST(self) -> None:
                if not self._authorized():
                    self._forbidden()
                    return
                path = urlparse(self.path).path
                length = int(self.headers.get("Content-Length") or 0)
                if length > 64_000:
                    self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, b"too large", "text/plain")
                    return
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw or b"{}")
                except Exception:
                    payload = {}
                if path == "/api/play":
                    sound_id = str(payload.get("id", ""))
                    if sound_id:
                        outer._play(sound_id)
                        self._json({"ok": True})
                    else:
                        self._json({"ok": False, "error": "missing id"})
                elif path == "/api/stop":
                    outer._stop()
                    self._json({"ok": True})
                else:
                    self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

        server = ThreadingHTTPServer((self.bind, self.port), Handler)
        server.daemon_threads = True
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        self._thread = None
