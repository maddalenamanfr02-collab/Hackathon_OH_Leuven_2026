"""Metadata_Component — build, validate, and assign sensitivity.

Two channels (per design):
  - build(): fatal rejection for missing required fields or invalid dates (R3.7/R3.8)
  - validate(): non-fatal warnings; warned records are still stored (R4.*)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .model import (OPTIONAL_FIELDS, REQUIRED_FIELDS, DocumentRecord,
                    is_nonblank, parse_iso_date)


@dataclass
class FieldError:
    id: str
    field: str
    reason: str


@dataclass
class BuildOutcome:
    record: DocumentRecord | None
    rejected: bool
    rejection_errors: list[FieldError] = field(default_factory=list)


@dataclass
class Warning:
    id: str
    field: str
    message: str


@dataclass
class ValidationReport:
    warnings: list[Warning] = field(default_factory=list)

    def ids_with_warnings(self) -> set[str]:
        return {w.id for w in self.warnings}


def build(doc_id: str, source_row: dict, suggestion: dict,
          overrides: dict | None = None) -> BuildOutcome:
    """Combine CSV values + enrichment suggestion + operator overrides."""
    overrides = overrides or {}

    def pick(name: str, default=""):
        if name in overrides:
            return overrides[name]
        if source_row.get(name) not in (None, ""):
            return source_row[name]
        if suggestion.get(name) not in (None, ""):
            return suggestion[name]
        return default

    keywords = overrides.get("keywords", suggestion.get("keywords") or [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    rec = DocumentRecord(
        id=doc_id,
        genre=(source_row.get("genre") or "").strip(),
        language=(source_row.get("language") or "").strip(),
        location=str(pick("location")).strip(),
        date=str(pick("date")).strip(),
        author=str(pick("author")).strip(),
        subcategory=str(pick("subcategory")).strip(),
        keywords=list(keywords),
        sensitivity_label=str(pick("sensitivity_label", "public")).strip() or "public",
        document_version=str(pick("document_version", "1.0")).strip() or "1.0",
        logical_identity=str(pick("logical_identity", doc_id)).strip() or doc_id,
        enrichment_source=suggestion.get("_source", ""),
    )

    errors: list[FieldError] = []
    for f in REQUIRED_FIELDS:
        if not is_nonblank(getattr(rec, f)):
            errors.append(FieldError(doc_id, f, "missing or blank required field"))

    if is_nonblank(rec.date) and parse_iso_date(rec.date) is None:
        errors.append(FieldError(doc_id, "date", f"invalid ISO date: {rec.date!r}"))

    if rec.sensitivity_label not in ("public", "restricted"):
        rec.sensitivity_label = "public"

    if errors:
        return BuildOutcome(record=None, rejected=True, rejection_errors=errors)
    return BuildOutcome(record=rec, rejected=False)


def validate(records: list[DocumentRecord]) -> ValidationReport:
    report = ValidationReport()
    for rec in records:
        for f in REQUIRED_FIELDS:
            if not is_nonblank(getattr(rec, f)):
                report.warnings.append(Warning(rec.id, f, f"missing required field {f}"))
        if is_nonblank(rec.date) and parse_iso_date(rec.date) is None:
            report.warnings.append(Warning(rec.id, "date", f"invalid date value {rec.date!r}"))
        # keyword bounds (soft)
        if rec.keywords and (len(rec.keywords) > 50 or
                             any(not (1 <= len(k.strip()) <= 100) for k in rec.keywords)):
            report.warnings.append(Warning(rec.id, "keywords", "keywords out of bounds"))
    return report
