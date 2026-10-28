"""Minimal zero-dependency web UI (stdlib http.server).

Single search box + results list; opens the Original_Rendering on click. Serves
entirely from the Local_Store — no external calls (R8.1 server-free on a laptop).
"""
from __future__ import annotations

import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .search import Filters, SearchEngine
from .store import verify_integrity

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MSF Document Retrieval</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
 h1{font-size:1.4rem}form{display:flex;gap:.5rem;margin:1rem 0}
 input[type=search]{flex:1;padding:.7rem;font-size:1.1rem;border:1px solid #bbb;border-radius:6px}
 button{padding:.7rem 1.2rem;font-size:1.1rem;border:0;border-radius:6px;background:#c8102e;color:#fff;cursor:pointer}
 .r{border:1px solid #e3e3e3;border-radius:8px;padding:.8rem 1rem;margin:.6rem 0}
 .r h3{margin:.1rem 0;font-size:1.05rem}.meta{color:#555;font-size:.85rem}
 .tag{display:inline-block;background:#f1f1f1;border-radius:4px;padding:.05rem .4rem;margin-right:.3rem;font-size:.75rem}
 .banner{background:#eef6ff;border:1px solid #cfe3ff;padding:.5rem .8rem;border-radius:6px;font-size:.85rem}
 .msg{color:#666}
</style></head><body>
<h1>👩‍⚕️ MSF Document Retrieval <span class="meta">offline-first</span></h1>
<p class="banner">Served entirely from local data — works without internet.</p>
<form method="get" action="/">
 <input type="search" name="q" placeholder="Search guidelines, reports, field accounts…" value="{q}" autofocus>
 <button type="submit">Search</button>
</form>
{body}
</body></html>"""


def _render_results(resp) -> str:
    if resp.message:
        return f'<p class="msg">{html.escape(resp.message)}</p>'
    out = [f'<p class="meta">{len(resp.results)} result(s)</p>']
    for r in resp.results[:50]:
        auth = "authoritative" if r.is_authoritative else "superseded"
        out.append(
            f'<div class="r"><h3><a href="/doc/{html.escape(r.id)}">{html.escape(r.title)}</a></h3>'
            f'<div class="meta">{html.escape(r.location)} · {html.escape(r.date)} · '
            f'{html.escape(r.author)}</div>'
            f'<div><span class="tag">{html.escape(r.genre)}</span>'
            f'<span class="tag">{html.escape(r.language)}</span>'
            f'<span class="tag">{html.escape(r.sensitivity_label)}</span>'
            f'<span class="tag">{auth}</span></div></div>')
    return "\n".join(out)


def make_handler(store_dir: Path):
    engine = SearchEngine(store_dir)
    renderings = store_dir / "renderings"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/":
                qs = urllib.parse.parse_qs(parsed.query)
                q = (qs.get("q", [""])[0]).strip()
                body = ""
                if q:
                    body = _render_results(engine.search(q, Filters()))
                page = PAGE.format(q=html.escape(q), body=body)
                self._send(200, page, "text/html; charset=utf-8")
            elif parsed.path.startswith("/doc/"):
                doc_id = urllib.parse.unquote(parsed.path[len("/doc/"):])
                match = next((p for p in renderings.glob(f"{doc_id}.*")), None)
                if not match:
                    self._send(404, "Document unavailable (no stored rendering).",
                               "text/plain; charset=utf-8")
                    return
                ctype = "application/pdf" if match.suffix == ".pdf" else "text/html; charset=utf-8"
                self._send_bytes(200, match.read_bytes(), ctype)
            elif parsed.path == "/api/search":
                qs = urllib.parse.parse_qs(parsed.query)
                resp = engine.search(qs.get("q", [""])[0], Filters())
                self._send(200, json.dumps(resp.to_dict()), "application/json")
            else:
                self._send(404, "Not found", "text/plain")

        def _send(self, code, text, ctype):
            self._send_bytes(code, text.encode("utf-8"), ctype)

        def _send_bytes(self, code, data, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(store_dir: Path, port: int = 8000) -> None:
    res = verify_integrity(store_dir)
    if not res.ok:
        raise SystemExit(f"Local_Store failed integrity check: {res.message}")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store_dir))
    print(f"MSF Document Retrieval UI on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    httpd.serve_forever()
