"""Local_Store — relocatable directory with SQLite+FTS5 index, metadata JSON,
renderings, manifest (checksums + run version), and reports.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .model import DocumentRecord

DB_NAME = "retrieval.db"
META_NAME = "metadata.json"
MANIFEST_NAME = "manifest.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def build_store(store_dir: Path, records: list[DocumentRecord],
                texts: dict[str, str], renderings: dict[str, Path] | None = None,
                reports: dict | None = None) -> dict:
    """Create the Local_Store. Returns the manifest dict."""
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / "renderings").mkdir(exist_ok=True)
    (store_dir / "reports").mkdir(exist_ok=True)

    db_path = store_dir / DB_NAME
    if db_path.exists():
        db_path.unlink()
    conn = _connect(db_path)
    conn.executescript(
        """
        CREATE TABLE documents (
          id TEXT PRIMARY KEY, genre TEXT, language TEXT, location TEXT,
          date TEXT, author TEXT, subcategory TEXT, keywords TEXT,
          sensitivity_label TEXT NOT NULL DEFAULT 'public',
          document_version TEXT, logical_identity TEXT,
          is_authoritative INTEGER NOT NULL, schema_version INTEGER NOT NULL,
          text_source TEXT, title TEXT
        );
        CREATE INDEX idx_logical ON documents(logical_identity);
        CREATE INDEX idx_sens ON documents(sensitivity_label);
        CREATE INDEX idx_date ON documents(date);
        CREATE VIRTUAL TABLE documents_fts USING fts5(
          id UNINDEXED, searchable_text,
          genre, language, location, subcategory, keywords, author,
          tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )
    for rec in records:
        conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec.id, rec.genre, rec.language, rec.location, rec.date, rec.author,
             rec.subcategory, json.dumps(rec.keywords), rec.sensitivity_label,
             rec.document_version, rec.logical_identity, int(rec.is_authoritative),
             rec.schema_version, rec.text_source, rec.title),
        )
        conn.execute(
            "INSERT INTO documents_fts (id, searchable_text, genre, language, "
            "location, subcategory, keywords, author) VALUES (?,?,?,?,?,?,?,?)",
            (rec.id, texts.get(rec.id, ""), rec.genre, rec.language, rec.location,
             rec.subcategory, " ".join(rec.keywords), rec.author),
        )
    conn.commit()
    conn.close()

    # metadata.json — human-readable source of truth
    meta_path = store_dir / META_NAME
    meta_path.write_text(
        json.dumps([r.to_dict() for r in records], indent=2, ensure_ascii=False),
        encoding="utf-8")

    # copy renderings named by id stem
    if renderings:
        for doc_id, src in renderings.items():
            if src and src.exists():
                shutil.copy2(src, store_dir / "renderings" / f"{doc_id}{src.suffix.lower()}")

    if reports:
        for name, payload in reports.items():
            (store_dir / "reports" / name).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # manifest: run version/date + checksums (R12.2, R13.4)
    manifest = {
        "run_version": _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "document_count": len(records),
        "checksums": {
            DB_NAME: _sha256(db_path),
            META_NAME: _sha256(meta_path),
        },
    }
    (store_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


@dataclass
class IntegrityResult:
    ok: bool
    corrupted_artifacts: list[str] = field(default_factory=list)
    message: str = ""


def verify_integrity(store_dir: Path) -> IntegrityResult:
    manifest_path = store_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return IntegrityResult(False, [MANIFEST_NAME], "manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corrupted: list[str] = []
    for name, expected in manifest.get("checksums", {}).items():
        p = store_dir / name
        if not p.exists() or _sha256(p) != expected:
            corrupted.append(name)
    # SQLite's own check
    db_path = store_dir / DB_NAME
    if db_path.exists():
        try:
            conn = _connect(db_path)
            row = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if row and row[0] != "ok":
                corrupted.append(DB_NAME)
        except sqlite3.DatabaseError:
            corrupted.append(DB_NAME)
    if corrupted:
        return IntegrityResult(False, corrupted, f"corrupted: {', '.join(corrupted)}")
    return IntegrityResult(True, [], "ok")
