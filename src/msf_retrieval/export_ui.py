"""Export the Local_Store into a static documents.js for the web UI.

The colleague's frontend (app.js) consumes a window.MSF_DOCUMENTS array of records
shaped as { id, title, summary, languages: [...], genre }. This exporter reads
the SQLite index and emits that array as a plain JS file, so the UI runs fully
offline with real data and no backend/API (consistent with the offline-first,
server-free design).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .store import DB_NAME

# app.js language filter values; everything else collapses to "und" (Unknown).
_KNOWN_LANGS = {"en", "fr", "ar", "es"}


def _summary(text: str, keywords: list[str], limit: int = 280) -> str:
    text = " ".join((text or "").split())
    if text:
        return text[:limit] + ("…" if len(text) > limit else "")
    if keywords:
        return "Keywords: " + ", ".join(keywords)
    return "No summary available."


def build_records(store_dir: Path) -> list[dict]:
    conn = sqlite3.connect(store_dir / DB_NAME)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT d.id, d.genre, d.language, d.location, d.date, d.author, "
        "d.keywords, d.sensitivity_label, d.is_authoritative, d.title AS stored_title, "
        "(SELECT searchable_text FROM documents_fts f WHERE f.id = d.id) AS text "
        "FROM documents d WHERE d.sensitivity_label != 'restricted'").fetchall()
    records = []
    for r in rows:
        lang = r["language"] if r["language"] in _KNOWN_LANGS else "und"
        keywords = json.loads(r["keywords"] or "[]")
        stored = (r["stored_title"] or "").strip() if "stored_title" in r.keys() else ""
        title = stored or f'{r["genre"]} — {r["location"]} ({r["date"]})'
        records.append({
            "id": r["id"],
            "title": title,
            "summary": _summary(r["text"], keywords),
            "languages": [lang],
            "genre": r["genre"] or "unknown",
            # extra fields the UI ignores today but a richer adapter can use
            "location": r["location"],
            "date": r["date"],
            "author": r["author"],
            "keywords": keywords,
        })
    conn.close()
    records.sort(key=lambda x: x["date"], reverse=True)
    return records


def export(store_dir: Path, out_path: Path) -> int:
    records = build_records(store_dir)
    payload = json.dumps(records, ensure_ascii=False, indent=1)
    banner = ("/* Auto-generated from the Local_Store by `msf-retrieval export`.\n"
              " * Do not edit by hand. Regenerate after rebuilding the index.\n"
              " * Provides the real `documents` collection consumed by app.js. */\n")
    out_path.write_text(f"{banner}window.MSF_DOCUMENTS = {payload};\n", encoding="utf-8")
    return len(records)
