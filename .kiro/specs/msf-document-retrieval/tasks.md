# Implementation Plan: MSF Document Retrieval

## Overview

This plan implements the two-stage MSF Document Retrieval system in Python 3.11+ (stdlib `csv`/`json`/`sqlite3`, Hypothesis for property-based tests), exactly as specified in the design. It builds up from data models and the human-readable `Local_Store`, through the one-time Ingestion & Enrichment stage (corpus walk, text extraction, Bedrock enrichment, metadata build/validate/sensitivity, version resolution, SQLite+FTS5 index build, manifest/checksums), then the always-local Search & Retrieval stage (integrity verification, FTS search with sensitivity + authoritative + metadata filtering, retrieval/UI surface), and finally wires the full ingestion→store→serve pipeline together.

Each correctness property from the design is implemented as a single Hypothesis property-based test (minimum 100 iterations), placed next to the code it verifies and tagged `Feature: msf-document-retrieval, Property {n}`. Property test sub-tasks are marked optional with `*`; core implementation and wiring tasks are not.

## Tasks

- [ ] 1. Set up project structure, data models, and test scaffolding
  - [ ] 1.1 Create the project skeleton and shared types
    - Create package directories `msf_retrieval/` (with `ingestion/`, `enrichment/`, `metadata/`, `index/`, `store/`, `search/`, `retrieval/`) and `tests/` (with `property/`, `unit/`, `integration/`, `generators/`)
    - Define the `Enriched_Schema` `DocumentRecord` data model with every field from the data-model table (`id`, `genre`, `language`, `location`, `date`, `author`, `subcategory`, `keywords`, `sensitivity_label`, `document_version`, `logical_identity`, `is_authoritative`, `schema_version`) plus `enrichment_source` and `text_source`
    - Define the shared result/error/report dataclasses: `IngestionResult`, `IngestedDocument`, `IngestionError` (with `kind` enum), `ExtractResult`, `EnrichmentSuggestion`, `PartialMetadata`, `BuildOutcome`, `FieldError`, `ValidationReport`, `Warning`, `IntegrityResult`, `Filters`, `UserContext`, `SearchResponse`, `ResultItem`
    - Configure the Hypothesis test runner (min 100 iterations profile) and the unit/integration test layout
    - _Requirements: 3.1, 13.2_

  - [ ] 1.2 Build the domain generators used by the property tests
    - Write Hypothesis strategies for `Source_CSV` rows, corpora with injectable per-document faults, `DocumentRecord`s with controllable missing/whitespace required fields and optional-field presence, valid/invalid dates (boundaries 1899-12-31, 1900-01-01, 2099-12-31, 2100-01-01), keyword lists at boundary sizes (0/1/50/51 terms; 100/101-char terms), versioned logical-identity groups, mixed-sensitivity corpora, queries plus filters, and `Local_Store` directories (with byte-flipping for integrity tests)
    - Include all-whitespace strings and non-ASCII text in string strategies
    - _Requirements: 3.1_

- [ ] 2. Implement the human-readable Local_Store and metadata serialization
  - [ ] 2.1 Implement the Local_Store directory layout and metadata.json read/write
    - Create the `store` module that defines/initializes the relocatable directory layout (`manifest.json`, `metadata.json`, `retrieval.db`, `renderings/`, `reports/`)
    - Implement `DocumentRecord` <-> `metadata.json` serialization as a JSON array, treating a missing optional key as empty on read and writing `schema_version` on every record
    - _Requirements: 12.1, 13.2, 13.3_

  - [ ]* 2.2 Write property test for metadata serialization round-trip
    - **Property 30: Metadata serialization round-trips in a human-readable format**
    - Tag: `Feature: msf-document-retrieval, Property 30`
    - **Validates: Requirements 13.2**

  - [ ]* 2.3 Write property test for additive schema evolution
    - **Property 31: Additive schema evolution is backward compatible**
    - Read a record written under an earlier `schema_version` lacking a later optional field; assert it loads without error and treats the field as empty
    - Tag: `Feature: msf-document-retrieval, Property 31`
    - **Validates: Requirements 13.3**

- [ ] 3. Implement text extraction
  - [ ] 3.1 Implement the Text Extractor
    - Implement `extract(rendering) -> ExtractResult` with HTML markup/script stripping and PDF text-layer extraction, returning `ok=false` with a `failure_cause` when no text can be extracted (e.g., image-only PDF)
    - _Requirements: 2.3, 2.4_

  - [ ]* 3.2 Write unit tests for the Text Extractor
    - Test HTML stripping, PDF text-layer extraction, and the image-only/no-text-layer failure path
    - _Requirements: 2.3, 2.4_

- [ ] 4. Implement the Ingestion_Component
  - [ ] 4.1 Implement corpus walk, id association, and duplicate handling
    - Implement `ingest(source_csv, corpus_root) -> IngestionResult` walking rows in `Source_CSV` order; associate each ingested document with its row id; on the first occurrence of an id ingest it, on later occurrences emit one `duplicate_id` error and skip
    - Maintain the invariant that `ingested_count + failed_count` equals the number of distinct referenced ids
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [ ] 4.2 Implement searchable-text source selection and rendering retention
    - Prefer plain text when it has at least one non-whitespace character; otherwise extract from the HTML/PDF format via the Text Extractor; always copy the HTML/PDF rendering into `Local_Store/renderings/`; record `text_source` on each `IngestedDocument`
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 4.3 Implement fail-soft error handling and the ingestion report
    - Emit the correct `IngestionError` kind for missing content, unreadable content, extraction failure, and no usable format; exclude extraction/no-format cases from indexing; never terminate the run; write `reports/ingestion_report.json`
    - _Requirements: 1.4, 1.5, 2.4, 2.5_

  - [ ]* 4.4 Write property test for full id accounting
    - **Property 1: Ingestion accounts for every id exactly once**
    - Tag: `Feature: msf-document-retrieval, Property 1`
    - **Validates: Requirements 1.1, 1.2, 1.6**

  - [ ]* 4.5 Write property test for duplicate-id handling
    - **Property 2: Duplicate ids keep the first row and report the rest**
    - Tag: `Feature: msf-document-retrieval, Property 2`
    - **Validates: Requirements 1.3**

  - [ ]* 4.6 Write property test for searchable-text source selection
    - **Property 4: Searchable-text source selection**
    - Tag: `Feature: msf-document-retrieval, Property 4`
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement the Metadata_Component (build, date/keywords rules, sensitivity)
  - [ ] 6.1 Implement date and keywords validation helpers
    - Implement an ISO `YYYY-MM-DD` parser that accepts only valid calendar dates in 1900-01-01…2099-12-31 and round-trips the stored string, and a keywords validator requiring 1–50 terms each non-empty and 1–100 chars after trimming
    - _Requirements: 3.5, 3.6, 3.8_

  - [ ] 6.2 Implement record build with required-field enforcement and rejection channel
    - Implement `build(id, source_row, suggestion, overrides) -> BuildOutcome`: populate `id`/`genre`/`language` from the `Source_CSV` row, fill remaining fields from suggestion/overrides, store absent optional fields as empty, and reject (fatal) any record missing/whitespace-only required fields or carrying an invalid/out-of-range date, naming each offending field in `rejection_errors`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 3.8_

  - [ ] 6.3 Implement sensitivity assignment
    - Implement `assign_sensitivity(record)` assigning one of `public`|`restricted`, defaulting to `public` when the source metadata has no explicit label
    - _Requirements: 9.1, 9.2_

  - [ ]* 6.4 Write property test for accepted-record field completeness and provenance
    - **Property 5: Accepted records have a complete, well-formed field set with correct provenance**
    - Tag: `Feature: msf-document-retrieval, Property 5`
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

  - [ ]* 6.5 Write property test for required-field completeness at build time
    - **Property 6: Required-field completeness is enforced at build time**
    - Tag: `Feature: msf-document-retrieval, Property 6`
    - **Validates: Requirements 3.7**

  - [ ]* 6.6 Write property test for date validity and round-trip
    - **Property 7: Date validity and round-trip**
    - Tag: `Feature: msf-document-retrieval, Property 7`
    - **Validates: Requirements 3.5, 3.8**

  - [ ]* 6.7 Write property test for keywords bounds
    - **Property 8: Keywords bounds**
    - Tag: `Feature: msf-document-retrieval, Property 8`
    - **Validates: Requirements 3.6**

  - [ ]* 6.8 Write property test for every-record-carries-sensitivity default
    - **Property 23: Every record carries a sensitivity label, defaulting to public**
    - Tag: `Feature: msf-document-retrieval, Property 23`
    - **Validates: Requirements 9.1, 9.2**

- [ ] 7. Implement metadata validation (warning channel)
  - [ ] 7.1 Implement validation and the validation report
    - Implement `validate(records) -> ValidationReport`: one warning per missing required field (naming id and field), one warning per non-ISO date value (naming id and the value), zero entries when all records are clean, and no warnings for missing optional fields; keep warned records storable and indexable (warnings are non-fatal and mutually exclusive with build-time rejection); write `reports/validation_report.json`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 7.2 Write property test for validation-warning completeness
    - **Property 9: Validation-warning completeness**
    - Tag: `Feature: msf-document-retrieval, Property 9`
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [ ]* 7.3 Write property test for missing optional fields never warning
    - **Property 10: Missing optional fields never warn**
    - Tag: `Feature: msf-document-retrieval, Property 10`
    - **Validates: Requirements 4.4**

  - [ ]* 7.4 Write property test for warned records still stored and indexed
    - **Property 11: Warned records are still stored and indexed**
    - Tag: `Feature: msf-document-retrieval, Property 11`
    - **Validates: Requirements 4.5**

- [ ] 8. Implement the Version Resolver
  - [ ] 8.1 Implement logical-identity grouping and authoritative selection
    - Implement `resolve(records) -> list[DocumentRecord]`: group by `logical_identity`, select exactly one authoritative record per group (highest `document_version`, ties broken by most recent `date`, then by id), and set `is_authoritative` on every record
    - _Requirements: 10.1, 10.2_

  - [ ]* 8.2 Write property test for exactly one authoritative version per identity
    - **Property 25: Exactly one authoritative version per logical identity**
    - Tag: `Feature: msf-document-retrieval, Property 25`
    - **Validates: Requirements 10.1, 10.2**

- [ ] 9. Implement the Enrichment Service (one-time, Amazon Bedrock) with caching
  - [ ] 9.1 Implement the Bedrock Converse enrichment client
    - Implement `enrich(id, searchable_text, known) -> EnrichmentSuggestion` using the Bedrock Converse API on `bedrock-runtime`, always setting `maxTokens` explicitly, using a low-cost model, with exponential-backoff-and-jitter retry on throttling/transient errors and graceful degradation (leave fields unfilled so required-field validation decides the record's fate) on persistent failure
    - Treat suggestions as inputs to `Metadata_Component.build` (never direct index writes); honor operator overrides
    - _Requirements: 8.3_

  - [ ] 9.2 Implement the enrichment cache
    - Write every suggestion to `reports/enrichment_cache.json` (and surface into `metadata.json` via build); on re-run, reuse cached suggestions for unchanged documents so no new Bedrock calls are issued
    - _Requirements: 8.3, 13.1_

  - [ ]* 9.3 Write property test for one-time cached enrichment
    - **Property 22: One-time enrichment is cached, re-runs cost nothing**
    - Use a mocked Bedrock client and assert zero external calls on re-run over an unchanged corpus
    - Tag: `Feature: msf-document-retrieval, Property 22`
    - **Validates: Requirements 8.3**

  - [ ]* 9.4 Write unit test asserting maxTokens is always set
    - Assert every Converse call sets `maxTokens` explicitly (mocked client)
    - _Requirements: 8.3_

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement the Index Builder (SQLite + FTS5) and manifest
  - [ ] 11.1 Create the SQLite schema and index build
    - Implement `build(records, texts) -> BuildReport`: create the `documents` relational table (with `idx_logical`, `idx_sens`, `idx_date` indexes) and the `documents_fts` FTS5 virtual table (`unicode61 remove_diacritics 2`); include every ingested record (including empty-searchable-text records via metadata only); exclude and report records whose indexing fails; keep the build deterministic so an unchanged corpus yields the identical set of ids; persist `retrieval.db` into the `Local_Store`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 11.2 Write the manifest with run version/date and checksums
    - Write `manifest.json` recording the ingestion run version/date and per-artifact checksums for `retrieval.db`, `metadata.json`, and renderings
    - _Requirements: 13.4, 12.2_

  - [ ]* 11.3 Write property test for fail-soft single-document faults (incl. indexing failure)
    - **Property 3: Single-document faults are fail-soft**
    - Exercise missing/unreadable content, extraction failure, no usable format, and indexing failure via the fault-injecting corpus generator
    - Tag: `Feature: msf-document-retrieval, Property 3`
    - **Validates: Requirements 1.4, 1.5, 2.4, 2.5, 5.3**

  - [ ]* 11.4 Write property test for index coverage matching ingested documents
    - **Property 12: Index coverage matches ingested documents**
    - Tag: `Feature: msf-document-retrieval, Property 12`
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 11.5 Write property test for deterministic index build
    - **Property 13: Index build is deterministic over an unchanged corpus**
    - Tag: `Feature: msf-document-retrieval, Property 13`
    - **Validates: Requirements 5.5**

  - [ ]* 11.6 Write unit test for index persistence to the Local_Store path
    - Assert `retrieval.db` exists at the expected `Local_Store` path after a build
    - _Requirements: 5.4_

  - [ ]* 11.7 Write unit test for manifest run version/date
    - Assert `manifest.json` records the ingestion run version/date
    - _Requirements: 13.4_

- [ ] 12. Implement the Integrity Verifier
  - [ ] 12.1 Implement startup integrity verification
    - Implement `verify(store) -> IntegrityResult`: recompute checksums of `retrieval.db`, `metadata.json`, and renderings against `manifest.json`, run SQLite `PRAGMA integrity_check`, and report `ok` only when all artifacts match and the DB check passes, listing corrupted artifacts otherwise
    - _Requirements: 12.2, 12.3_

  - [ ]* 12.2 Write property test for integrity detection soundness and withholding
    - **Property 27: Startup integrity detection is sound and withholds corrupted results**
    - Use byte-flipping on store artifacts; assert success iff artifacts match and the DB check passes, and that corrupted-data results are withheld
    - Tag: `Feature: msf-document-retrieval, Property 27`
    - **Validates: Requirements 12.2, 12.3**

- [ ] 13. Implement the Search_Component
  - [ ] 13.1 Implement query validation and FTS search with ranking
    - Implement `search(query, filters, user) -> SearchResponse`: reject empty/whitespace query with no filters (prompt message, no search); run FTS match ranked by descending matched-query-term count with more-recent-date tie-break; populate every `ResultItem` display field (`id`, title/identifier, `genre`, `language`, `location`, `date`, `author`, `sensitivity_label`, `is_authoritative`)
    - _Requirements: 6.1, 6.7, 6.8, 9.4, 10.3, 10.5, 11.1, 11.2_

  - [ ] 13.2 Implement conjunctive metadata filters, date range, sensitivity, and authoritative filtering
    - Apply all metadata filters (genre, language, location, subcategory, keywords, author) as SQL conjunctions and an inclusive date range; exclude `restricted` records for unauthorized users within the SQL predicate (identical online/offline); return only authoritative versions unless `include_superseded` is set
    - _Requirements: 6.2, 6.3, 9.3, 9.5, 10.4_

  - [ ] 13.3 Implement no-match and local-serving behavior
    - Return an empty result set with no-match/broaden guidance when nothing matches; set `served_from_local` and the local-data message; ensure search reads exclusively from the `Local_Store` with zero external calls and withholds results flagged corrupted by the Integrity Verifier
    - _Requirements: 6.6, 7.1, 7.2, 8.2, 8.4, 11.4, 12.4_

  - [ ]* 13.4 Write property test for conjunctive filters and inclusive date range
    - **Property 14: Metadata filters are conjunctive and date ranges inclusive**
    - Tag: `Feature: msf-document-retrieval, Property 14`
    - **Validates: Requirements 6.2, 6.3**

  - [ ]* 13.5 Write property test for ranking order
    - **Property 15: Ranking is non-increasing in matched-term count, recency breaks ties**
    - Tag: `Feature: msf-document-retrieval, Property 15`
    - **Validates: Requirements 6.1, 10.5**

  - [ ]* 13.6 Write property test for empty/whitespace query not searching
    - **Property 16: Empty or whitespace-only query without filters does not search**
    - Tag: `Feature: msf-document-retrieval, Property 16`
    - **Validates: Requirements 6.7**

  - [ ]* 13.7 Write property test for no-match results with guidance
    - **Property 17: No-match queries return empty results with guidance**
    - Tag: `Feature: msf-document-retrieval, Property 17`
    - **Validates: Requirements 6.6, 11.4**

  - [ ]* 13.8 Write property test for required display fields on results
    - **Property 18: Result items expose the required display fields**
    - Tag: `Feature: msf-document-retrieval, Property 18`
    - **Validates: Requirements 6.8, 9.4, 10.3, 11.2**

  - [ ]* 13.9 Write property test for no external call during search
    - **Property 19: Search issues no external call, online or offline**
    - Tag: `Feature: msf-document-retrieval, Property 19`
    - **Validates: Requirements 7.1, 8.2, 8.4, 12.4**

  - [ ]* 13.10 Write property test for offline text availability
    - **Property 20: Offline text availability**
    - Tag: `Feature: msf-document-retrieval, Property 20`
    - **Validates: Requirements 7.2**

  - [ ]* 13.11 Write property test for sensitivity enforcement online and offline
    - **Property 24: Sensitivity enforcement is identical online and offline**
    - Tag: `Feature: msf-document-retrieval, Property 24`
    - **Validates: Requirements 9.3, 9.5**

  - [ ]* 13.12 Write property test for default authoritative-only queries
    - **Property 26: Default queries return only authoritative versions**
    - Tag: `Feature: msf-document-retrieval, Property 26`
    - **Validates: Requirements 10.4**

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Implement the Retrieval / UI surface and network fallback
  - [ ] 15.1 Implement result selection and rendering access
    - Implement opening the stored HTML/PDF rendering for a selected result; when the rendering is missing or won't open, preserve the current result list and show a "document unavailable" message; present a single search box that returns results with no required configuration and a human-readable title/id per result
    - _Requirements: 6.4, 6.5, 11.1, 11.2_

  - [ ] 15.2 Implement the bounded optional-network path with local fallback
    - Implement the optional best-effort network call bounded by a 5-second budget; on timeout/offline complete from the `Local_Store`, preserve the session and active query state, and flag `served_from_local` to drive the local-data indication; resume the network path after restoration without requiring a restart or re-entering the query
    - _Requirements: 7.3, 7.4, 7.5_

  - [ ]* 15.3 Write property test for network-timeout local fallback with preserved state
    - **Property 21: Network timeout falls back to local with preserved state and a local-data indication**
    - Tag: `Feature: msf-document-retrieval, Property 21`
    - **Validates: Requirements 7.3, 7.4**

  - [ ]* 15.4 Write unit tests for rendering access and unavailable message
    - Test that selecting a present rendering opens it, and that a missing rendering preserves the list and shows the unavailable message
    - _Requirements: 6.4, 6.5_

- [ ] 16. Wire the full pipeline together
  - [ ] 16.1 Implement the one-time ingestion orchestrator
    - Create an `ingest` entry point that runs Ingestion_Component -> Text Extractor -> Enrichment Service -> Metadata_Component (build + validate + sensitivity) -> Version Resolver -> Index Builder, writing `metadata.json`, `retrieval.db`, renderings, `manifest.json`, and all `reports/` into a single `Local_Store` directory; support additive re-ingestion that preserves unchanged prior records
    - _Requirements: 5.1, 8.3, 13.1, 13.4_

  - [ ] 16.2 Implement the serving orchestrator
    - Create a `serve` entry point that runs the Integrity Verifier at startup against an existing `Local_Store`, withholds results on corruption, and otherwise exposes the Search_Component and Retrieval/UI surface operating entirely from the local directory
    - _Requirements: 8.1, 12.2, 12.3, 12.4_

  - [ ]* 16.3 Write property test for additive re-ingestion
    - **Property 29: Re-ingestion is additive and preserves prior records**
    - Tag: `Feature: msf-document-retrieval, Property 29`
    - **Validates: Requirements 13.1**

  - [ ]* 16.4 Write property test for relocatable Local_Store
    - **Property 28: Local_Store is relocatable without re-ingestion**
    - Copy the entire store directory and assert queries from the copy match the original with no re-ingestion
    - Tag: `Feature: msf-document-retrieval, Property 28`
    - **Validates: Requirements 12.1**

  - [ ]* 16.5 Write end-to-end offline integration test
    - Ingest a small fixture corpus against a mocked Bedrock client, build the store, then search with the network disabled; assert results, sensitivity enforcement, authoritative-only defaults, the local-data flag, and that search never invokes the Bedrock client
    - _Requirements: 7.1, 8.1, 9.3, 10.4_

  - [ ]* 16.6 Write connectivity-restoration integration test
    - Simulate network loss then restoration; assert the session and active query survive and the network path resumes without a restart
    - _Requirements: 7.5_

- [ ] 17. Add the performance benchmark
  - [ ]* 17.1 Write the scale/latency benchmark
    - Build a `Local_Store` of up to 10,000 documents and assert median and worst-case query latency under 3 seconds (kept out of property tests)
    - _Requirements: 6.1, 7.1, 11.3_

- [ ] 18. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (property tests, unit tests, integration tests, benchmark) and can be skipped for a faster MVP; core implementation and wiring tasks are never optional.
- Each of the 31 correctness properties maps to exactly one Hypothesis property-based test, tagged `Feature: msf-document-retrieval, Property {n}`, configured for a minimum of 100 iterations, and placed next to the code it verifies.
- Build-time rejection (fatal) and validation warnings (non-fatal) are kept mutually exclusive: rejection happens first, only surviving records reach validation and are stored/indexed with any warnings retained.
- Bedrock enrichment is one-time and cached; the serving stage reads exclusively from the `Local_Store` with zero per-query external calls, so sensitivity and authoritative filtering behave identically online and offline.
- Checkpoints ensure incremental validation across the ingestion, metadata, index/search, and wiring stages.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4", "4.5", "4.6", "6.1", "6.3"] },
    { "id": 5, "tasks": ["6.2", "8.1", "9.1"] },
    { "id": 6, "tasks": ["6.4", "6.5", "6.6", "6.7", "6.8", "7.1", "8.2", "9.2"] },
    { "id": 7, "tasks": ["7.2", "7.3", "7.4", "9.3", "9.4", "11.1"] },
    { "id": 8, "tasks": ["11.2", "11.3", "11.4", "11.5", "11.6", "11.7", "12.1"] },
    { "id": 9, "tasks": ["12.2", "13.1"] },
    { "id": 10, "tasks": ["13.2", "13.3"] },
    { "id": 11, "tasks": ["13.4", "13.5", "13.6", "13.7", "13.8", "13.9", "13.10", "13.11", "13.12", "15.1", "15.2"] },
    { "id": 12, "tasks": ["15.3", "15.4", "16.1", "16.2"] },
    { "id": 13, "tasks": ["16.3", "16.4", "16.5", "16.6", "17.1"] }
  ]
}
```
