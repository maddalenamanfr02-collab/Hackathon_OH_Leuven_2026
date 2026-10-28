"""Core data model for the Enriched_Schema (Document_Record)."""
from __future__ import annotations

import dataclasses
import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

SCHEMA_VERSION = 1

REQUIRED_FIELDS = ("id", "genre", "language", "location", "date", "author")
OPTIONAL_FIELDS = ("subcategory", "keywords")

MIN_DATE = _dt.date(1900, 1, 1)
MAX_DATE = _dt.date(2099, 12, 31)


@dataclass
class DocumentRecord:
    """One enriched metadata entry conforming to the Enriched_Schema."""

    id: str
    genre: str
    language: str
    location: str
    date: str  # ISO 8601 YYYY-MM-DD
    author: str
    subcategory: str = ""
    keywords: list[str] = field(default_factory=list)
    sensitivity_label: str = "public"  # public | restricted
    document_version: str = "1.0"
    logical_identity: str = ""
    is_authoritative: bool = True
    schema_version: int = SCHEMA_VERSION
    title: str = ""  # optional human-provided title (e.g. from upload)
    # provenance, not part of the required schema
    enrichment_source: str = ""
    text_source: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DocumentRecord":
        # Backward-compatible read: ignore unknown keys, default missing ones
        # (R13.3 additive schema evolution).
        known = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in known}
        filtered.setdefault("logical_identity", filtered.get("id", ""))
        return cls(**filtered)


def is_nonblank(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def parse_iso_date(value: str) -> Optional[_dt.date]:
    """Return a date iff value is a valid YYYY-MM-DD within [1900, 2099]."""
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        return None
    try:
        d = _dt.date.fromisoformat(value)
    except ValueError:
        return None
    if d < MIN_DATE or d > MAX_DATE:
        return None
    return d
