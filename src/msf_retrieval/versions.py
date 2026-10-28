"""Version Resolver — one Authoritative_Version per logical identity (R10)."""
from __future__ import annotations

from .model import DocumentRecord, parse_iso_date


def _version_key(rec: DocumentRecord):
    # Parse a dotted version like "2.0" -> (2, 0) for comparison; fall back to 0.
    parts = []
    for p in str(rec.document_version).split("."):
        parts.append(int(p) if p.isdigit() else 0)
    d = parse_iso_date(rec.date)
    return (tuple(parts), d.isoformat() if d else "", rec.id)


def resolve(records: list[DocumentRecord]) -> list[DocumentRecord]:
    groups: dict[str, list[DocumentRecord]] = {}
    for rec in records:
        groups.setdefault(rec.logical_identity or rec.id, []).append(rec)

    for group in groups.values():
        winner = max(group, key=_version_key)
        for rec in group:
            rec.is_authoritative = rec is winner
    return records
