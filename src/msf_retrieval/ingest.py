"""Ingestion_Component — walk the corpus and resolve files by id stem.

For each row in documentation.csv it resolves:
  Original/<id>.html | Original/<id>.pdf   (the single human-readable rendering)
  Parsed/<id>.md                            (the searchable-text source)
Fail-soft: any single-document fault is recorded and the run continues.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from . import extract


@dataclass
class IngestedDocument:
    id: str
    source_row: dict
    searchable_text: str
    text_source: str  # parsed_markdown | extracted_original
    rendering_path: Path | None


@dataclass
class IngestionError:
    id: str
    kind: str  # duplicate_id|missing_content|unreadable_content|extraction_failure|no_usable_format
    detail: str


@dataclass
class IngestionResult:
    ingested: list[IngestedDocument] = field(default_factory=list)
    errors: list[IngestionError] = field(default_factory=list)

    @property
    def ingested_count(self) -> int:
        return len(self.ingested)

    @property
    def failed_count(self) -> int:
        # Count distinct failed ids (a doc may trigger one failure).
        return len({e.id for e in self.errors if e.kind != "duplicate_id"}) + \
            len([e for e in self.errors if e.kind == "duplicate_id"])


def _find_original(original_dir: Path, doc_id: str) -> Path | None:
    for ext in (".html", ".htm", ".pdf"):
        p = original_dir / f"{doc_id}{ext}"
        if p.exists():
            return p
    return None


def ingest(source_csv: Path, corpus_root: Path) -> IngestionResult:
    """corpus_root contains Original/ and Parsed/ subdirectories."""
    original_dir = corpus_root / "Original"
    parsed_dir = corpus_root / "Parsed"
    result = IngestionResult()
    seen: set[str] = set()

    with source_csv.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            doc_id = (row.get("id") or "").strip()
            if not doc_id:
                continue
            if doc_id in seen:
                result.errors.append(IngestionError(doc_id, "duplicate_id",
                                                     "id repeated in Source_CSV; first row kept"))
                continue
            seen.add(doc_id)

            md_path = parsed_dir / f"{doc_id}.md"
            original = _find_original(original_dir, doc_id)

            searchable = ""
            text_source = ""

            # Prefer Parsed_Markdown.
            if md_path.exists():
                try:
                    md_text = md_path.read_text(encoding="utf-8", errors="replace")
                    if md_text.strip():
                        searchable = md_text
                        text_source = "parsed_markdown"
                except OSError as exc:
                    result.errors.append(IngestionError(doc_id, "unreadable_content", str(exc)))
                    continue

            # Fallback: extract from the Original_Rendering.
            if not searchable:
                if original is None:
                    if md_path.exists():
                        # md existed but was blank and no original -> no usable format
                        result.errors.append(IngestionError(
                            doc_id, "no_usable_format", "blank parsed markdown and no original"))
                    else:
                        result.errors.append(IngestionError(
                            doc_id, "missing_content", "no parsed markdown and no original file"))
                    continue
                ex = extract.extract(original)
                if not ex.ok:
                    result.errors.append(IngestionError(doc_id, "extraction_failure", ex.failure_cause or ""))
                    continue
                searchable = ex.text
                text_source = "extracted_original"

            result.ingested.append(IngestedDocument(
                id=doc_id, source_row=dict(row), searchable_text=searchable,
                text_source=text_source, rendering_path=original))

    return result
