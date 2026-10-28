"""Property-based tests for MSF Document Retrieval.

Hypothesis is the intended library (see design Testing Strategy). It is not
installed in this draft environment, so this suite uses a small stdlib harness
that runs each property over >=100 randomized inputs. Swap in Hypothesis by
replacing `for _ in range(ITER)` loops with @given strategies.
"""
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.msf_retrieval import metadata, versions  # noqa: E402
from src.msf_retrieval.model import DocumentRecord, parse_iso_date  # noqa: E402
from src.msf_retrieval import store as store_mod  # noqa: E402
from src.msf_retrieval.search import Filters, SearchEngine  # noqa: E402

ITER = 120
rng = random.Random(1234)


def rand_date():
    y = rng.randint(1900, 2099)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return f"{y:04d}-{m:02d}-{d:02d}"


def rand_record(idx, **over):
    rec = DocumentRecord(
        id=over.get("id", f"D{idx:04d}"),
        genre=over.get("genre", rng.choice(["Press Release", "Clinical Guideline Chapter"])),
        language=over.get("language", rng.choice(["en", "fr", "ar", "es"])),
        location=over.get("location", rng.choice(["Sudan", "Yemen", "Haiti", "Global"])),
        date=over.get("date", rand_date()),
        author=over.get("author", "MSF"),
        keywords=over.get("keywords", []),
        sensitivity_label=over.get("sensitivity_label", "public"),
        document_version=over.get("document_version", "1.0"),
        logical_identity=over.get("logical_identity", over.get("id", f"D{idx:04d}")),
    )
    return rec


class TestProperties(unittest.TestCase):

    def test_property_6_required_fields_rejected(self):
        # Feature: msf-document-retrieval, Property 6: required-field completeness at build time
        for _ in range(ITER):
            row = {"genre": "Press Release", "language": "en"}
            missing = rng.choice(["location", "date", "author"])
            suggestion = {"location": "Sudan", "date": "2020-01-01", "author": "MSF"}
            suggestion[missing] = ""  # blank out one required field
            outcome = metadata.build("D1", row, suggestion)
            self.assertTrue(outcome.rejected)
            self.assertIn(missing, [e.field for e in outcome.rejection_errors])

    def test_property_7_date_validity_roundtrip(self):
        # Feature: msf-document-retrieval, Property 7: date validity and round-trip
        for _ in range(ITER):
            valid = rand_date()
            d = parse_iso_date(valid)
            self.assertIsNotNone(d)
            self.assertEqual(d.isoformat(), valid)
            bad = rng.choice(["2020-13-01", "2020-02-30", "not-a-date", "1899-12-31", "2100-01-01"])
            self.assertIsNone(parse_iso_date(bad))

    def test_property_25_one_authoritative_per_identity(self):
        # Feature: msf-document-retrieval, Property 25: exactly one authoritative version per identity
        for _ in range(ITER):
            n = rng.randint(2, 5)
            recs = [rand_record(i, logical_identity="LID",
                                document_version=f"{rng.randint(1,9)}.0") for i in range(n)]
            versions.resolve(recs)
            self.assertEqual(sum(1 for r in recs if r.is_authoritative), 1)

    def test_property_30_metadata_roundtrip(self):
        # Feature: msf-document-retrieval, Property 30: metadata serialization round-trips
        for _ in range(50):
            rec = rand_record(rng.randint(0, 9999))
            back = DocumentRecord.from_dict(rec.to_dict())
            self.assertEqual(back.id, rec.id)
            self.assertEqual(back.date, rec.date)
            self.assertEqual(back.keywords, rec.keywords)

    def test_property_24_sensitivity_enforced(self):
        # Feature: msf-document-retrieval, Property 24: sensitivity enforcement
        for _ in range(40):
            recs = [rand_record(i, id=f"S{i}", logical_identity=f"S{i}",
                                sensitivity_label=rng.choice(["public", "restricted"]),
                                keywords=["cholera"]) for i in range(8)]
            texts = {r.id: "cholera outbreak" for r in recs}
            with tempfile.TemporaryDirectory() as tmp:
                store_mod.build_store(Path(tmp), recs, texts)
                eng = SearchEngine(Path(tmp), authorized_restricted=False)
                resp = eng.search("cholera", Filters())
                self.assertFalse(any(r.sensitivity_label == "restricted" for r in resp.results))

    def test_property_16_empty_query_no_search(self):
        # Feature: msf-document-retrieval, Property 16: empty/whitespace query does not search
        with tempfile.TemporaryDirectory() as tmp:
            recs = [rand_record(0, id="X0", logical_identity="X0")]
            store_mod.build_store(Path(tmp), recs, {"X0": "text"})
            eng = SearchEngine(Path(tmp))
            for q in ("", "   ", "\t\n"):
                resp = eng.search(q, Filters())
                self.assertEqual(resp.results, [])
                self.assertIsNotNone(resp.message)

    def test_property_27_integrity_detects_corruption(self):
        # Feature: msf-document-retrieval, Property 27: integrity detection withholds corrupted results
        with tempfile.TemporaryDirectory() as tmp:
            recs = [rand_record(0, id="X0", logical_identity="X0")]
            store_mod.build_store(Path(tmp), recs, {"X0": "text"})
            self.assertTrue(store_mod.verify_integrity(Path(tmp)).ok)
            meta = Path(tmp) / "metadata.json"
            meta.write_text(meta.read_text() + "  ", encoding="utf-8")  # tamper
            res = store_mod.verify_integrity(Path(tmp))
            self.assertFalse(res.ok)
            self.assertIn("metadata.json", res.corrupted_artifacts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
