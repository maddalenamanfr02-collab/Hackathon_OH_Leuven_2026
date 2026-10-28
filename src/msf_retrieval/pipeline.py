"""End-to-end ingestion + enrichment + indexing orchestrator."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from . import ingest, metadata, versions
from .enrich import HeuristicEnricher


def run_ingestion(source_csv: Path, corpus_root: Path, store_dir: Path,
                  enricher=None, limit: int | None = None,
                  uploads_dir: Path | None = None) -> dict:
    from . import store as store_mod  # local import to avoid cycles

    enricher = enricher or HeuristicEnricher()
    ing = ingest.ingest(source_csv, corpus_root)

    docs = ing.ingested[:limit] if limit else ing.ingested

    uploaded = []
    if uploads_dir is not None:
        up = ingest.ingest_folder(uploads_dir)
        ing.errors.extend(up.errors)
        uploaded = up.ingested
    all_docs = list(docs) + list(uploaded)

    records = []
    texts: dict[str, str] = {}
    renderings: dict[str, Path] = {}
    rejections = []

    import datetime as _dt
    today = _dt.date.today().isoformat()
    for doc in all_docs:
        suggestion = enricher.enrich(doc.id, doc.searchable_text, doc.source_row)
        is_upload = doc.id.startswith('UP-')
        if is_upload:
            # Guarantee uploaded files are indexable: fill required fields.
            suggestion.setdefault('location', suggestion.get('location') or 'Uploaded')
            suggestion['date'] = suggestion.get('date') or today
            suggestion['author'] = suggestion.get('author') or 'Uploaded'
        outcome = metadata.build(doc.id, doc.source_row, suggestion)
        if outcome.rejected:
            rejections.extend(asdict(e) for e in outcome.rejection_errors)
            continue
        rec = outcome.record
        rec.text_source = doc.text_source
        records.append(rec)
        texts[rec.id] = doc.searchable_text
        if doc.rendering_path:
            renderings[rec.id] = doc.rendering_path

    versions.resolve(records)
    report = metadata.validate(records)

    reports = {
        "ingestion_report.json": {
            "ingested_count": ing.ingested_count,
            "failed_count": ing.failed_count,
            "errors": [asdict(e) for e in ing.errors],
            "rejections": rejections,
        },
        "validation_report.json": {
            "warnings": [asdict(w) for w in report.warnings],
        },
    }
    manifest = store_mod.build_store(store_dir, records, texts, renderings, reports)

    return {
        "ingested": ing.ingested_count + len(uploaded),
        "failed": ing.failed_count,
        "indexed": len(records),
        "uploaded": len(uploaded),
        "rejected": len(rejections),
        "warnings": len(report.warnings),
        "run_version": manifest["run_version"],
    }
