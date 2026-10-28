# MSF Document Retrieval

Offline-first, cost-effective document search for Médecins Sans Frontières (MSF)
field staff. Built for the **Hackathon OH Leuven 2026**.

It ingests the MSF corpus (`documentation.csv` + the `Original/` renderings and
`Parsed/` Markdown), enriches each document with richer metadata (location,
date, author, keywords, sensitivity, version), builds a single-file SQLite +
FTS5 index, and serves fast search that works with **no internet connection**.

The full specification lives in `.kiro/specs/msf-document-retrieval/`
(requirements, design, and implementation tasks).

## Why this design

- **Offline-first.** All search is served from a local SQLite+FTS5 store — zero
  per-query network calls. Works for days or weeks without connectivity.
- **Cost-effective.** No server to run; the UI is a stdlib `http.server`. Any
  LLM enrichment is a one-time ingestion step whose results are cached locally.
- **Rugged / relocatable.** The whole `local_store/` directory can be copied to
  another device and served without re-ingesting. Startup integrity check guards
  against corruption from rough transport.
- **Two-stage.** Expensive, network-capable ingestion runs once; the field-facing
  search path is always local.

## Requirements

- Python 3.11+ (tested on 3.14). Standard library only — **no dependencies**
  required to build and search.
- Optional: `boto3` to enable Amazon Bedrock enrichment (otherwise a fully
  offline heuristic enricher is used).

## Usage

Build the local index from the corpus (one-time):

```bash
python3 -m src.msf_retrieval.cli build --store local_store
# add --limit 50 for a quick trial
```

Search from the command line:

```bash
python3 -m src.msf_retrieval.cli search "tuberculosis treatment" --store local_store
python3 -m src.msf_retrieval.cli search "cholera" --genre "Clinical Guideline Chapter"
```

Check the store's integrity:

```bash
python3 -m src.msf_retrieval.cli verify --store local_store
```

Launch the minimal web UI (then open http://127.0.0.1:8000):

```bash
python3 -m src.msf_retrieval.cli serve --store local_store --port 8000
```

## Tests

Property-based tests (stdlib harness; Hypothesis-ready) covering the design's
correctness properties:

```bash
python3 -m unittest tests.test_properties -v
```

## Project structure

| Path | Description |
| --- | --- |
| `src/msf_retrieval/model.py` | Enriched_Schema data model + date/field rules |
| `src/msf_retrieval/ingest.py` | Corpus walk, id→file resolution, fail-soft ingestion |
| `src/msf_retrieval/extract.py` | HTML/PDF text extraction fallback |
| `src/msf_retrieval/enrich.py` | Offline heuristic enricher + Bedrock stub |
| `src/msf_retrieval/metadata.py` | Build (reject) + validate (warn) + sensitivity |
| `src/msf_retrieval/versions.py` | Authoritative-version resolver |
| `src/msf_retrieval/store.py` | SQLite+FTS5 index, manifest, integrity verifier |
| `src/msf_retrieval/search.py` | Query + metadata filters + ranking |
| `src/msf_retrieval/pipeline.py` | End-to-end ingestion orchestrator |
| `src/msf_retrieval/web.py` | Minimal zero-dependency web UI |
| `src/msf_retrieval/cli.py` | `build` / `search` / `verify` / `serve` commands |

## Data

The corpus lives under `shared_documents/` (not required to read this README):
`documentation.csv` plus `D4GC data/D4GC data/{Original,Parsed}/`.
For the hackathon, all provided documents are publicly available.
