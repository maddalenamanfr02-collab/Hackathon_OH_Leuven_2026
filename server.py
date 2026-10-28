"""Standalone server for the MSF Library web UI.

Requires Python 3.11+ stdlib only — no pip installs.

Architecture
------------
This server simulates the field hardware scenario:

  "Hardware" = shared_documents/Uploaded documents/
    A folder that represents the shared network drive all field laptops can
    reach. When a user clicks Upload, files land here. Anyone on the local
    network could add files here too (that's the "pull" side of sync).

  Upload  (POST /api/upload)
    Browser sends files → saved into shared_documents/Uploaded documents/
    Nothing else happens yet. The file is on the "hardware".

  Sync    (POST /api/sync)
    Reads everything in shared_documents/Uploaded documents/ (your own
    uploads AND any new files others put there since your last sync), then:
      1. Copies each file into D4GC data/Original/
      2. Extracts text and writes D4GC data/Parsed/<stem>.md
      3. Re-runs the ingestion pipeline → rebuilds local_store/retrieval.db
      4. Regenerates documents.js (the data the Search tab reads)
      5. Clears the staging folder
      6. Returns the updated document list so the browser refreshes Search
         WITHOUT a page reload.

  GET /api/sync/status
    Returns pending file list so the Sync panel shows live counts.

  GET /api/documents
    Returns the current window.MSF_DOCUMENTS array as JSON so the browser
    can hot-reload the search collection after a sync.

Usage
-----
    python server.py            # http://127.0.0.1:8000
    python server.py --port 9000
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import shutil
import sqlite3
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT         = Path(__file__).parent.resolve()
CORPUS_ROOT  = ROOT / "shared_documents" / "D4GC data" / "D4GC data"
ORIGINAL_DIR = CORPUS_ROOT / "Original"
PARSED_DIR   = CORPUS_ROOT / "Parsed"
UPLOAD_DIR   = ROOT / "shared_documents" / "Uploaded documents"
STORE_DIR    = ROOT / "local_store"
SOURCE_CSV   = ROOT / "shared_documents" / "documentation.csv"
DOCUMENTS_JS = ROOT / "documents.js"
DB_PATH      = STORE_DIR / "retrieval.db"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js":   "text/javascript; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".svg":  "image/svg+xml",
    ".json": "application/json",
    ".pdf":  "application/pdf",
    ".png":  "image/png",
    ".ico":  "image/x-icon",
}

# ────────────────────────────────────────────────────────────────────────────
# Multipart parser (stdlib only — cgi.FieldStorage removed in 3.13)
# ────────────────────────────────────────────────────────────────────────────

def _parse_multipart(content_type: str, body: bytes) -> list[tuple[str, bytes]]:
    m = re.search(r'boundary=("?)([^";\s]+)\1', content_type, re.I)
    if not m:
        return []
    boundary = m.group(2).encode()
    results: list[tuple[str, bytes]] = []
    for part in body.split(b"--" + boundary)[1:]:
        if part.strip() in (b"", b"--", b"--\r\n"):
            continue
        sep = b"\r\n\r\n" if b"\r\n\r\n" in part else b"\n\n"
        if sep not in part:
            continue
        raw_headers, data = part.split(sep, 1)
        data = data.rstrip(b"\r\n")
        if data.endswith(b"--"):
            data = data[:-2].rstrip(b"\r\n")
        headers_text = raw_headers.decode("utf-8", errors="replace")
        fn = re.search(r'filename\*?=(?:"([^"]+)"|([^\s;]+))', headers_text, re.I)
        if fn:
            results.append((fn.group(1) or fn.group(2), data))
    return results

# ────────────────────────────────────────────────────────────────────────────
# Text extraction (mirrors src/msf_retrieval/extract.py — no import needed)
# ────────────────────────────────────────────────────────────────────────────

import html as _html_mod
import zlib
from html.parser import HTMLParser

class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "head", "noscript"}
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._depth = 0
    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP: self._depth += 1
    def handle_endtag(self, tag):
        if tag in self._SKIP and self._depth: self._depth -= 1
    def handle_data(self, data):
        if self._depth == 0 and data.strip(): self._chunks.append(data)
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._chunks)).strip()

def _extract_html(raw: str) -> str:
    p = _HTMLText(); p.feed(raw); return p.text()

def _extract_pdf(data: bytes) -> str:
    chunks: list[str] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        blob = m.group(1)
        try: blob = zlib.decompress(blob)
        except zlib.error: pass
        for t in re.finditer(rb"\((?:[^()\\]|\\.)*\)", blob):
            s = t.group(0)[1:-1].replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            try: chunks.append(s.decode("latin-1"))
            except Exception: continue
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()

def _extract(path: Path) -> str:
    try:
        if path.suffix.lower() in (".html", ".htm"):
            return _extract_html(path.read_text(encoding="utf-8", errors="replace"))
        elif path.suffix.lower() == ".pdf":
            return _extract_pdf(path.read_bytes())
    except OSError:
        pass
    return ""

# ────────────────────────────────────────────────────────────────────────────
# Heuristic enricher (mirrors src/msf_retrieval/enrich.py)
# ────────────────────────────────────────────────────────────────────────────

_LOCATIONS = [
    "Democratic Republic of the Congo", "South Sudan", "Sudan", "Yemen", "Syria",
    "Afghanistan", "Nigeria", "Ethiopia", "Somalia", "Bangladesh", "Myanmar",
    "Haiti", "Central African Republic", "Chad", "Mali", "Niger", "Iraq",
    "Lebanon", "Ukraine", "Gaza", "Palestine", "India", "Mozambique", "Kenya",
    "Uganda", "Tanzania", "Mediterranean", "Greece", "Libya", "Venezuela",
]
_DATE_RE = re.compile(r"\b(19|20)\d{2}\b")
_MONTHS  = "january february march april may june july august september october november december".split()
_STOP    = set("the a an and or of to in for on with by is are was were be this that "
               "from at as it its their our we you they he she his her not no but if "
               "which who whom whose can may will shall should would could more most "
               "than then them these those into over under about after before".split())

from collections import Counter as _Counter

def _enrich(text: str) -> dict:
    low = text.lower()
    location = next((l for l in _LOCATIONS if l.lower() in low), "Global")
    date = ""
    m = _DATE_RE.search(text)
    if m:
        year = m.group(0)
        window = text[max(0, m.start()-20): m.end()+10].lower()
        month = next((i+1 for i, n in enumerate(_MONTHS) if n in window), 1)
        date = f"{year}-{month:02d}-01"
    if not date:
        date = _dt.date.today().isoformat()
    keywords = [w for w, _ in _Counter(
        w for w in re.findall(r"[a-zA-Z]{4,}", low) if w not in _STOP
    ).most_common(8)]
    return {"location": location, "date": date, "author": "MSF", "keywords": keywords}

# ────────────────────────────────────────────────────────────────────────────
# Incremental SQLite index update
# ────────────────────────────────────────────────────────────────────────────

def _ensure_db() -> sqlite3.Connection:
    """Open (or create) the SQLite+FTS5 database."""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            genre TEXT, language TEXT, location TEXT,
            date TEXT, author TEXT, keywords TEXT,
            sensitivity_label TEXT NOT NULL DEFAULT 'public',
            is_authoritative INTEGER NOT NULL DEFAULT 1,
            schema_version INTEGER NOT NULL DEFAULT 1,
            text_source TEXT, title TEXT
        );
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at TEXT NOT NULL,
            filename TEXT NOT NULL,
            doc_id TEXT NOT NULL
        );
    """)
    # FTS virtual table — create separately so IF NOT EXISTS works cleanly.
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                id UNINDEXED, searchable_text,
                genre, language, location, keywords, author,
                tokenize = 'unicode61 remove_diacritics 2'
            )
        """)
    except sqlite3.OperationalError:
        pass  # FTS5 not available — search will still work via metadata
    conn.commit()
    return conn


def _index_document(conn: sqlite3.Connection, doc_id: str, title: str,
                    text: str, genre: str, location: str, date: str,
                    author: str, keywords: list[str], text_source: str):
    """Insert or replace one document in the index."""
    conn.execute(
        "INSERT OR REPLACE INTO documents "
        "(id, genre, language, location, date, author, keywords, "
        " sensitivity_label, is_authoritative, schema_version, text_source, title) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (doc_id, genre, "und", location, date, author,
         json.dumps(keywords), "public", 1, 1, text_source, title),
    )
    # FTS: delete old entry first, then re-insert.
    conn.execute("DELETE FROM documents_fts WHERE id = ?", (doc_id,))
    try:
        conn.execute(
            "INSERT INTO documents_fts (id, searchable_text, genre, language, "
            "location, keywords, author) VALUES (?,?,?,?,?,?,?)",
            (doc_id, text, genre, "und", location, " ".join(keywords), author),
        )
    except sqlite3.OperationalError:
        pass  # FTS5 unavailable


# ────────────────────────────────────────────────────────────────────────────
# documents.js builder  (keeps existing records + adds new ones)
# ────────────────────────────────────────────────────────────────────────────

_KNOWN_LANGS = {"en", "fr", "ar", "es"}

def _load_existing_documents_js() -> list[dict]:
    """Parse the existing documents.js and return the records array.
    Returns an empty list if the file is missing or unparseable."""
    if not DOCUMENTS_JS.exists():
        return []
    try:
        content = DOCUMENTS_JS.read_text(encoding="utf-8")
        # Strip the JS assignment wrapper: window.MSF_DOCUMENTS = [...];
        m = re.search(r'window\.MSF_DOCUMENTS\s*=\s*(\[.*\])\s*;', content, re.DOTALL)
        if m:
            return json.loads(m.group(1))
    except Exception:
        pass
    return []


def _rebuild_documents_js(conn: sqlite3.Connection) -> list[dict]:
    """Merge newly indexed (uploaded) documents into the existing documents.js.

    The original collection (from the git-tracked documents.js) is preserved.
    New uploaded documents are appended / updated by id so they appear in
    Search immediately after a sync.
    """
    # 1. Start from whatever is already in documents.js (original collection).
    existing = _load_existing_documents_js()
    existing_by_id = {r["id"]: r for r in existing}

    # 2. Pull every uploaded document from the SQLite index.
    rows = conn.execute(
        "SELECT d.id, d.genre, d.language, d.location, d.date, d.author, "
        "d.keywords, d.title, "
        "(SELECT searchable_text FROM documents_fts f WHERE f.id = d.id) AS text "
        "FROM documents d WHERE d.sensitivity_label != 'restricted'"
    ).fetchall()

    for r in rows:
        lang     = r["language"] if r["language"] in _KNOWN_LANGS else "und"
        keywords = json.loads(r["keywords"] or "[]")
        text     = (r["text"] or "").strip()
        summary  = (text[:280] + "…" if len(text) > 280 else text) if text else \
                   ("Keywords: " + ", ".join(keywords) if keywords else "No summary available.")
        stored_title = (r["title"] or "").strip()
        title = stored_title or f'{r["genre"] or "Document"} — {r["location"]} ({r["date"]})'
        existing_by_id[r["id"]] = {
            "id":        r["id"],
            "title":     title,
            "summary":   summary,
            "languages": [lang],
            "genre":     r["genre"] or "unknown",
            "location":  r["location"] or "",
            "date":      r["date"] or "",
            "author":    r["author"] or "",
            "keywords":  keywords,
        }

    # 3. Sort newest first and write out.
    merged = sorted(existing_by_id.values(), key=lambda x: x.get("date", ""), reverse=True)
    payload = json.dumps(merged, ensure_ascii=False, indent=1)
    DOCUMENTS_JS.write_text(
        "/* Auto-generated by server.py sync. Do not edit by hand. */\n"
        f"window.MSF_DOCUMENTS = {payload};\n",
        encoding="utf-8",
    )
    return merged

# ────────────────────────────────────────────────────────────────────────────
# API handlers
# ────────────────────────────────────────────────────────────────────────────

def api_upload(body: bytes, content_type: str) -> dict:
    """Save uploaded files to the hardware staging area."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    parts = _parse_multipart(content_type, body)
    if not parts:
        return {"saved": [], "errors": ["No files found in request"]}
    saved, errors = [], []
    for filename, data in parts:
        safe = Path(filename).name.replace("\x00", "").strip()
        if not safe:
            errors.append(f"Invalid filename: {filename!r}")
            continue
        if Path(safe).suffix.lower() not in (".pdf", ".html", ".htm"):
            errors.append(f"{safe}: only PDF and HTML files are accepted")
            continue
        try:
            (UPLOAD_DIR / safe).write_bytes(data)
            saved.append(safe)
            print(f"  [upload] saved → shared_documents/Uploaded documents/{safe}")
        except OSError as exc:
            errors.append(f"{safe}: {exc}")
    return {"saved": saved, "errors": errors}


def api_sync(queue: list) -> dict:
    """
    For each entry in the browser's local queue:
      1. Create a stub Original/<name> (we don't have the bytes server-side —
         the queue holds metadata only, so we write a placeholder and the real
         file can be added later via a full upload if needed)
      2. Extract text if a real file exists in UPLOAD_DIR, otherwise use metadata
      3. Write Parsed/<stem>.md
      4. Index into SQLite
    Then rebuild documents.js and return the fresh record list.

    `queue` is a list of dicts: {name, title, author, date, size}
    """
    ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    conn = _ensure_db()
    synced, errors = [], []
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()

    for entry in queue:
        name   = Path(entry.get("name", "")).name.replace("\x00", "").strip()
        title  = entry.get("title") or name
        author = entry.get("author") or "MSF"
        date   = entry.get("date") or _dt.date.today().isoformat()

        if not name:
            errors.append("empty filename in queue entry")
            continue

        try:
            stem = Path(name).stem

            # Check if the actual file was uploaded to the staging area.
            staged_file = UPLOAD_DIR / name if UPLOAD_DIR.exists() else None
            has_file = staged_file and staged_file.is_file()

            # 1. Copy/create stub in Original/
            dest_orig = ORIGINAL_DIR / name
            if has_file:
                shutil.copy2(staged_file, dest_orig)
                print(f"  [sync]   copied   → Original/{name}")
            elif not dest_orig.exists():
                # Write a minimal HTML placeholder so the path exists.
                dest_orig.write_text(
                    f"<html><body><h1>{title}</h1><p>Author: {author}</p>"
                    f"<p>Date: {date}</p></body></html>",
                    encoding="utf-8",
                )
                print(f"  [sync]   stub     → Original/{name} (no file bytes)")

            # 2. Extract text (prefer real file, fall back to metadata).
            if has_file:
                text = _extract(staged_file)
                enriched = _enrich(text or title)
            else:
                text = ""
                enriched = _enrich(title)

            # Override with the user-supplied metadata.
            enriched["author"] = author
            enriched["date"]   = date

            # 3. Write Parsed/<stem>.md
            stub_path = PARSED_DIR / f"{stem}.md"
            stub_content = (
                f"# {title}\n\n"
                f"**Author:** {author}  \n"
                f"**Date:** {date}  \n"
                f"**Location:** {enriched['location']}  \n"
                f"**Keywords:** {', '.join(enriched['keywords'])}  \n\n"
                + (text[:4000] if text else "_No extractable text — metadata only._")
            )
            stub_path.write_text(stub_content, encoding="utf-8")
            print(f"  [sync]   parsed   → Parsed/{stem}.md")

            # 4. Index into SQLite
            doc_id = "UP-" + stem
            _index_document(
                conn, doc_id,
                title=title,
                text=text or stub_content,
                genre="Uploaded Document",
                location=enriched["location"],
                date=date,
                author=author,
                keywords=enriched["keywords"],
                text_source="extracted_original" if has_file else "metadata",
            )
            conn.execute(
                "INSERT INTO sync_log (synced_at, filename, doc_id) VALUES (?,?,?)",
                (now_iso, name, doc_id),
            )
            conn.commit()
            synced.append(name)

            # Remove from staging area if it was there.
            if has_file:
                try:
                    staged_file.unlink(missing_ok=True)
                except OSError:
                    pass

        except Exception as exc:
            errors.append(f"{name}: {exc}")
            print(f"  [sync]   ERROR    {name}: {exc}", file=sys.stderr)

    # 5. Rebuild documents.js with ALL indexed documents.
    records = _rebuild_documents_js(conn)
    conn.close()
    print(f"  [sync]   documents.js updated — {len(records)} total records")

    return {
        "synced": synced,
        "errors": errors,
        "sync_time": now_iso,
        "total_documents": len(records),
        "records": records,
    }


def api_sync_status() -> dict:
    staged = sorted(UPLOAD_DIR.iterdir()) if UPLOAD_DIR.exists() else []
    staged = [f for f in staged if f.is_file()
              and f.suffix.lower() in (".pdf", ".html", ".htm")]
    mtime = None
    if staged:
        mtime = _dt.datetime.fromtimestamp(
            max(f.stat().st_mtime for f in staged), tz=_dt.timezone.utc
        ).isoformat()
    return {"pending": [f.name for f in staged], "count": len(staged), "latest_mtime": mtime}


def api_documents() -> list:
    """Return the current document list so the browser can hot-reload."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    records = _rebuild_documents_js(conn)
    conn.close()
    return records

# ────────────────────────────────────────────────────────────────────────────
# HTTP handler
# ────────────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)

        if path == "/api/sync/status":
            self._json(200, api_sync_status())
            return

        if path == "/api/documents":
            self._json(200, api_documents())
            return

        # Static file
        rel = path.lstrip("/") or "index.html"
        target = (ROOT / rel).resolve()
        if ROOT not in target.parents and target != ROOT:
            self._send(403, b"Forbidden", "text/plain")
            return
        if not target.is_file():
            self._send(404, b"Not found", "text/plain")
            return
        ctype = STATIC_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        if path == "/api/upload":
            ct = self.headers.get("Content-Type", "")
            self._json(200, api_upload(body, ct))
            return

        if path == "/api/sync":
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {}
            queue = payload.get("queue", [])
            self._json(200, api_sync(queue))
            return

        self._send(404, b"Not found", "text/plain")

    def _send(self, code: int, data: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, data, "application/json; charset=utf-8")

# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MSF Library server")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # Ensure staging folder exists.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # Pre-warm the database so it exists before the first request.
    conn = _ensure_db()
    conn.close()

    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"\n  MSF Library →  http://127.0.0.1:{args.port}")
    print(f"  Hardware staging:  {UPLOAD_DIR.relative_to(ROOT)}")
    print(f"  Original folder:   {ORIGINAL_DIR.relative_to(ROOT)}")
    print(f"  Parsed folder:     {PARSED_DIR.relative_to(ROOT)}")
    print(f"  Ctrl+C to stop\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
