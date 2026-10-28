"""Search_Component — serves queries entirely from the Local_Store (offline).

Zero per-query external calls. Sensitivity + authoritative filtering live in the
SQL predicate so results are identical online and offline.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .store import DB_NAME


@dataclass
class Filters:
    genre: str | None = None
    language: str | None = None
    location: str | None = None
    subcategory: str | None = None
    author: str | None = None
    keywords: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    include_superseded: bool = False

    def is_empty(self) -> bool:
        return not any([self.genre, self.language, self.location, self.subcategory,
                        self.author, self.keywords, self.date_from, self.date_to])


@dataclass
class ResultItem:
    id: str
    title: str
    genre: str
    language: str
    location: str
    date: str
    author: str
    sensitivity_label: str
    is_authoritative: bool


@dataclass
class SearchResponse:
    results: list[ResultItem] = field(default_factory=list)
    served_from_local: bool = True
    message: str | None = None

    def to_dict(self) -> dict:
        return {"results": [asdict(r) for r in self.results],
                "served_from_local": self.served_from_local,
                "message": self.message}


def _fts_query(raw: str) -> str:
    terms = re.findall(r"[^\s]+", raw)
    safe = [f'"{t}"' for t in terms if t]
    return " OR ".join(safe)


class SearchEngine:
    def __init__(self, store_dir: Path, authorized_restricted: bool = False):
        self._db = store_dir / DB_NAME
        self._authorized = authorized_restricted

    def search(self, query: str, filters: Filters | None = None) -> SearchResponse:
        filters = filters or Filters()
        query = (query or "").strip()

        if not query and filters.is_empty():
            return SearchResponse(message="Enter a search term or apply a filter to begin.")

        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row

        where = []
        params: list = []

        if query:
            where.append(
                "d.id IN (SELECT id FROM documents_fts WHERE documents_fts MATCH ?)")
            params.append(_fts_query(query))

        for col in ("genre", "language", "location", "subcategory", "author"):
            val = getattr(filters, col)
            if val:
                where.append(f"d.{col} = ?")
                params.append(val)
        if filters.date_from:
            where.append("d.date >= ?"); params.append(filters.date_from)
        if filters.date_to:
            where.append("d.date <= ?"); params.append(filters.date_to)
        if filters.keywords:
            for kw in filters.keywords:
                where.append("d.keywords LIKE ?"); params.append(f'%"{kw}"%')
        if not filters.include_superseded:
            where.append("d.is_authoritative = 1")
        if not self._authorized:
            where.append("d.sensitivity_label != 'restricted'")

        sql = "SELECT d.* FROM documents d"
        if where:
            sql += " WHERE " + " AND ".join(where)

        rows = conn.execute(sql, params).fetchall()

        # Rank by matched-term count (desc), recency (desc) as tie-break.
        terms = [t.lower() for t in re.findall(r"[^\s]+", query)]

        def score(row) -> int:
            if not terms:
                return 0
            hay = " ".join(str(row[c] or "") for c in
                           ("genre", "language", "location", "subcategory",
                            "author", "keywords")).lower()
            return sum(1 for t in terms if t in hay)

        ranked = sorted(rows, key=lambda r: (score(r), r["date"] or ""), reverse=True)

        results = [ResultItem(
            id=r["id"], title=f'{r["genre"]} — {r["id"]}', genre=r["genre"],
            language=r["language"], location=r["location"], date=r["date"],
            author=r["author"], sensitivity_label=r["sensitivity_label"],
            is_authoritative=bool(r["is_authoritative"])) for r in ranked]
        conn.close()

        if not results:
            return SearchResponse(message=(
                "No documents matched. Try fewer or broader terms, or remove a filter."))
        return SearchResponse(results=results)
