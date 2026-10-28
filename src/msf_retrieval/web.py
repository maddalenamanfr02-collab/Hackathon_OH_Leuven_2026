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
 <input type="search" name="q" placeholder="Search guidelines, reports, field accounts…" value="__Q__" autofocus>
 <button type="submit">Search</button>
</form>
__BODY__
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
                page = PAGE.replace("__Q__", html.escape(q)).replace("__BODY__", body)
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
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store_dir))
    print(f"MSF Document Retrieval UI on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    httpd.serve_forever()


# --- Static frontend server (serves the colleague's index.html + app.js) ------

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
    ".json": "application/json", ".pdf": "application/pdf",
    ".png": "image/png", ".ico": "image/x-icon",
}


def _parse_multipart(body: bytes, content_type: str):
    """Yield (filename, data) for each file part in a multipart/form-data body.

    Uses the stdlib email parser (cgi.FieldStorage was removed in Python 3.13).
    """
    import email
    from email.policy import default as default_policy

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    msg = email.message_from_bytes(header + body, policy=default_policy)
    for part in msg.iter_parts() if msg.is_multipart() else []:
        filename = part.get_filename()
        if filename:
            yield filename, part.get_payload(decode=True) or b""


def make_static_handler(web_root: Path, store_dir: Path, on_upload=None):
    renderings = store_dir / "renderings"
    root = web_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(parsed.path)

            # Open an original rendering by id (kept from the API design).
            if path.startswith("/doc/"):
                doc_id = path[len("/doc/"):]
                match = next((p for p in renderings.glob(f"{doc_id}.*")), None)
                if not match:
                    self._send(404, b"Document unavailable (no stored rendering).",
                               "text/plain; charset=utf-8")
                    return
                ctype = "application/pdf" if match.suffix == ".pdf" else "text/html; charset=utf-8"
                self._send(200, match.read_bytes(), ctype)
                return

            rel = path.lstrip("/") or "index.html"
            target = (root / rel).resolve()
            if root not in target.parents and target != root:
                self._send(403, b"Forbidden", "text/plain")
                return
            if not target.is_file():
                self._send(404, b"Not found", "text/plain")
                return
            ctype = _STATIC_TYPES.get(target.suffix.lower(), "application/octet-stream")
            self._send(200, target.read_bytes(), ctype)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/api/upload" or on_upload is None:
                self._send(404, b"Not found", "text/plain")
                return
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0) or 0)
            if "multipart/form-data" not in ctype or length <= 0:
                self._json(400, {"ok": False, "error": "expected multipart upload"})
                return
            body = self.rfile.read(length)
            try:
                files = list(_parse_multipart(body, ctype))
            except Exception as exc:  # malformed upload
                self._json(400, {"ok": False, "error": f"could not parse upload: {exc}"})
                return
            allowed = {".pdf", ".html", ".htm"}
            files = [(fn, data) for fn, data in files
                     if Path(fn).suffix.lower() in allowed and data]
            if not files:
                self._json(400, {"ok": False, "error": "no PDF/HTML files in upload"})
                return
            try:
                result = on_upload(files)
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"processing failed: {exc}"})
                return
            self._json(200, {"ok": True, **result})

        def _send(self, code, data, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, payload):
            self._send(code, json.dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8")

    return Handler


def serve_static(web_root: Path, store_dir: Path, port: int = 8000,
                 imports_dir: Path | None = None, csv: Path | None = None,
                 corpus: Path | None = None) -> None:
    res = verify_integrity(store_dir)
    if not res.ok:
        raise SystemExit(f"Local_Store failed integrity check: {res.message}")

    on_upload = None
    if imports_dir is not None and csv is not None and corpus is not None:
        from .pipeline import run_ingestion
        from .export_ui import export as _export_ui

        def on_upload(files):
            imports_dir.mkdir(parents=True, exist_ok=True)
            saved = []
            for filename, data in files:
                # Store under a safe, flattened name inside imports/.
                safe = Path(filename).name
                dest = imports_dir / safe
                dest.write_bytes(data)
                saved.append(safe)
            stats = run_ingestion(csv, corpus, store_dir, uploads_dir=imports_dir)
            _export_ui(store_dir, web_root / "documents.js")
            return {"saved": saved, "indexed": stats["indexed"],
                    "uploaded": stats.get("uploaded", 0)}

    ThreadingHTTPServer.allow_reuse_address = True
    handler = make_static_handler(web_root, store_dir, on_upload)
    # If the chosen port is busy (e.g. a previous server is still running),
    # fall back to the next few ports instead of crashing.
    httpd = None
    for candidate in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate), handler)
            port = candidate
            break
        except OSError as exc:
            import errno
            if exc.errno == errno.EADDRINUSE:
                print(f"port {candidate} is in use, trying {candidate + 1}\u2026")
                continue
            raise
    if httpd is None:
        raise SystemExit(f"No free port found in range {port}-{port + 19}. "
                         f"Stop old servers with: pkill -f 'msf_retrieval.cli serve'")
    print(f"MSF Library UI on http://127.0.0.1:{port}  (serving {web_root}, Ctrl+C to stop)")
    httpd.serve_forever()
