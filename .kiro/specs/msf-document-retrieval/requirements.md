# Requirements Document

## Introduction

MSF Document Retrieval is a cost-effective, offline-first search system that helps Médecins Sans Frontières (MSF) field staff quickly find the right information during humanitarian crises. The system ingests the provided corpus of publicly available MSF documents, that is, the set of documents described by the Source_CSV metadata file (`shared_documents/documentation.csv`, with columns id, genre, language). Each document exists in two forms: a single human-readable Original rendering in either HTML or PDF format, and a parsed plain-text version in Markdown that serves as the source of searchable text. The current CSV metadata is limited (id, genre, language), so the system enriches each document with a richer metadata schema and exposes a search interface that remains usable when internet access is intermittent or unavailable.

This is a hackathon project (Hackathon OH Leuven 2026) and favors a pragmatic, lightweight design: it must run with minimal infrastructure, degrade gracefully when connectivity is lost, and keep operating and maintenance cost low.

## Glossary

- **Retrieval_System**: The complete software solution that ingests, enriches, indexes, stores, and serves MSF documents to staff.
- **Ingestion_Component**: The part of the Retrieval_System that reads source documents and the CSV metadata and prepares them for indexing.
- **Metadata_Component**: The part of the Retrieval_System responsible for building, validating, and storing the enriched metadata schema.
- **Search_Component**: The part of the Retrieval_System that accepts a query and returns matching documents ranked by relevance.
- **Local_Store**: On-device storage (local index, metadata, and document text) that enables operation without network access.
- **Document**: A single MSF information item identified by a unique id, available as one Original human-readable rendering in either HTML or PDF format, together with a parsed plain-text version in Markdown that provides the searchable text. The id maps directly to the filename stem of both files (for example, id `P01` maps to `P01.md` and `P01.html`; id `D17e499ac0a` maps to `D17e499ac0a.md` and `D17e499ac0a.html`).
- **Document_Record**: The enriched metadata entry for one Document, conforming to the Enriched_Schema.
- **Source_CSV**: The single provided CSV file (`shared_documents/documentation.csv`) containing baseline metadata (id, genre, language) for the documents.
- **Original_Rendering**: The single human-readable version of a Document, stored in either HTML or PDF format, shown to the Staff_User.
- **Parsed_Markdown**: The parsed plain-text version of a Document, stored in Markdown, used as the source of searchable text.
- **Enriched_Schema**: The metadata model consisting of id, genre, language, location, date, subcategory (optional), keywords (optional), and author.
- **Staff_User**: An MSF field worker who searches for and reads documents.
- **Offline_Mode**: The state in which the Retrieval_System operates without any network connection.
- **Authoritative_Version**: The Document_Version designated as the current, correct version among versions sharing the same logical document identity.
- **Document_Version**: A specific revision of a Document identified by the Document id together with a version indicator.
- **Sensitivity_Label**: A classification assigned to a Document indicating its confidentiality level (e.g., public or restricted).

## Requirements

### Requirement 1: Ingest the document corpus

**User Story:** As an MSF knowledge manager, I want the system to ingest all documents referenced in the Source_CSV and their source metadata, so that field staff can search a complete and consistent corpus.

#### Acceptance Criteria

1. WHEN ingestion is started against the document corpus, THE Ingestion_Component SHALL read every Document referenced by a row in the Source_CSV.
2. WHEN a Document is ingested, THE Ingestion_Component SHALL associate the Document with the unique id taken from its Source_CSV row.
3. IF two or more Source_CSV rows reference the same id, THEN THE Ingestion_Component SHALL record each duplicated id in an ingestion error report and ingest only the first row bearing that id.
4. IF a Document referenced in the Source_CSV has no corresponding content file in any format, THEN THE Ingestion_Component SHALL record the id in the ingestion error report and continue ingesting the remaining documents.
5. IF a Document content file exists but cannot be read, THEN THE Ingestion_Component SHALL record the id in the ingestion error report and continue ingesting the remaining documents.
6. WHEN ingestion completes, THE Ingestion_Component SHALL report the count of successfully ingested documents and the count of failed documents, such that the two counts together account for every id referenced in the Source_CSV.

### Requirement 2: Handle both document formats

**User Story:** As an MSF knowledge manager, I want each document's Original_Rendering and Parsed_Markdown handled correctly, so that staff can read documents and the system can index searchable text reliably.

#### Acceptance Criteria

1. WHERE a Document has a Parsed_Markdown that contains at least one non-whitespace character, THE Ingestion_Component SHALL use the Parsed_Markdown as the source of searchable text content.
2. WHERE a Document has an Original_Rendering, THE Retrieval_System SHALL retain the Original_Rendering as the human-readable rendering offered to the Staff_User.
3. IF a Document is missing its Parsed_Markdown, or its Parsed_Markdown contains only whitespace characters, but the Document has an Original_Rendering, THEN THE Ingestion_Component SHALL extract searchable text from the Original_Rendering.
4. IF text extraction from a Document fails, THEN THE Ingestion_Component SHALL record an entry in the ingestion error report containing the Document identifier and an indication of the failure cause, exclude that Document from the searchable index, and continue ingesting the remaining documents without terminating.
5. IF a Document has neither a Parsed_Markdown nor an Original_Rendering, THEN THE Ingestion_Component SHALL record an entry in the ingestion error report containing the Document identifier and an indication that no usable format is present, exclude that Document from the searchable index, and continue ingesting the remaining documents without terminating.

### Requirement 3: Define and build the enriched metadata schema

**User Story:** As an MSF knowledge manager, I want a richer, well-organized metadata schema, so that staff can filter and find documents by meaningful attributes beyond genre and language.

#### Acceptance Criteria

1. THE Metadata_Component SHALL represent each Document_Record with the fields id, genre, language, location, date, subcategory, keywords, and author, where location denotes the country or region the Document pertains to, consistent with every Document being part of a country.
2. WHEN a Document_Record is built, THE Metadata_Component SHALL populate id, genre, and language from the Source_CSV.
3. THE Metadata_Component SHALL treat id, genre, language, location, date, and author as required fields of the Enriched_Schema, where a required field is satisfied only by a non-empty value containing at least one non-whitespace character.
4. THE Metadata_Component SHALL treat subcategory and keywords as optional fields of the Enriched_Schema, and WHEN an optional field has no value for a Document_Record, THE Metadata_Component SHALL store that field as empty without rejecting the Document_Record.
5. WHEN a date value is stored in a Document_Record, THE Metadata_Component SHALL store the date in ISO 8601 calendar-date format (YYYY-MM-DD) representing a valid calendar date in the range 1900-01-01 to 2099-12-31 inclusive.
6. WHEN a keywords value is present in a Document_Record, THE Metadata_Component SHALL store keywords as a list of 1 to 50 discrete non-empty terms, each term being 1 to 100 characters after trimming leading and trailing whitespace.
7. IF a Document_Record is built with one or more required fields missing or empty, THEN THE Metadata_Component SHALL reject the Document_Record, exclude it from the Enriched_Schema output, and produce an error indication identifying each missing required field.
8. IF a date value does not match the ISO 8601 format YYYY-MM-DD or does not represent a valid calendar date within the permitted range, THEN THE Metadata_Component SHALL reject the Document_Record, exclude it from the Enriched_Schema output, and produce an error indication identifying the invalid date field.

### Requirement 4: Validate enriched metadata

**User Story:** As an MSF knowledge manager, I want metadata validated during ingestion, so that incomplete or malformed records are surfaced rather than silently indexed.

#### Acceptance Criteria

1. IF any of the required Enriched_Schema fields (id, genre, language, location, date, author) is missing from a Document_Record, THEN THE Metadata_Component SHALL record one validation warning per missing field, each warning identifying the id and the missing field name.
2. IF a date value does not conform to ISO 8601 format, THEN THE Metadata_Component SHALL record a validation warning that identifies the id and the invalid date value.
3. WHEN validation of all Document_Records completes, THE Metadata_Component SHALL produce a validation report listing every id with one or more warnings and their warnings, and SHALL produce a report with zero warning entries when no Document_Record has a warning.
4. WHERE a Document_Record is missing an optional field, THE Metadata_Component SHALL store the Document_Record without recording a validation warning for that field.
5. WHEN a Document_Record has one or more validation warnings, THE Metadata_Component SHALL still store and index the Document_Record while retaining its warnings in the validation report.

### Requirement 5: Build a searchable index

**User Story:** As an MSF knowledge manager, I want the document text and metadata indexed, so that staff searches return relevant results quickly.

#### Acceptance Criteria

1. WHEN ingestion and enrichment complete for all successfully ingested Documents, THE Retrieval_System SHALL build a search index over the searchable text content and all Enriched_Schema fields of every successfully ingested Document.
2. IF a successfully ingested Document has no searchable text content, THEN THE Retrieval_System SHALL include that Document's id in the search index using its Enriched_Schema fields.
3. IF indexing a Document fails, THEN THE Retrieval_System SHALL exclude that Document from the search index, record its id in an error indication, and continue indexing the remaining Documents.
4. WHEN the search index build completes, THE Retrieval_System SHALL store the search index in the Local_Store.
5. WHEN the search index is rebuilt against an unchanged corpus, THE Retrieval_System SHALL produce an index covering the identical set of Document ids as the previous build.

### Requirement 6: Search and retrieve documents

**User Story:** As a Staff_User, I want to search by keyword and filter by metadata, so that I can quickly find the right document during a crisis.

#### Acceptance Criteria

1. WHEN a Staff_User submits a text query of 1 to 200 characters, THE Search_Component SHALL return, within 3 seconds, a list of Document_Records whose searchable text or metadata matches the query, ordered by descending count of matched query terms.
2. WHERE a Staff_User applies filters on one or more metadata fields (genre, language, location, subcategory, keywords, or author), THE Search_Component SHALL return only Document_Records that match every applied filter.
3. WHERE a Staff_User applies a date-range filter, THE Search_Component SHALL return only Document_Records whose date falls within the inclusive range.
4. WHEN a Staff_User selects a search result, THE Retrieval_System SHALL provide access to the Original_Rendering of the corresponding Document.
5. IF a Staff_User selects a search result whose stored Original_Rendering is missing or cannot be opened, THEN THE Retrieval_System SHALL preserve the current result list and display a message indicating that the document is unavailable.
6. IF a query matches no Document_Records, THEN THE Search_Component SHALL return an empty result set and a message indicating that no documents matched.
7. IF a Staff_User submits an empty or whitespace-only query with no filters applied, THEN THE Search_Component SHALL not execute a search and SHALL display a message prompting the Staff_User to enter a query or filter.
8. WHEN the Search_Component returns results, THE Search_Component SHALL include the id, genre, language, location, date, and author of each matching Document_Record.

### Requirement 7: Operate offline and resist intermittent connectivity

**User Story:** As a Staff_User working in a crisis zone, I want the system to keep working without reliable internet, so that I can find information when connectivity is lost.

#### Acceptance Criteria

1. WHILE the Retrieval_System is in Offline_Mode, THE Search_Component SHALL serve search and retrieval requests exclusively from the Local_Store, returning results within 3 seconds for a Local_Store containing up to 10,000 Documents.
2. WHILE the Retrieval_System is in Offline_Mode, THE Retrieval_System SHALL provide access to the searchable text content of every Document whose ingestion has completed successfully, from the Local_Store.
3. IF a network request during a search or retrieval operation does not receive a response within 5 seconds, THEN THE Retrieval_System SHALL complete the operation using the Local_Store and SHALL preserve the Staff_User's current session and query state.
4. WHEN the Retrieval_System completes a search or retrieval operation using the Local_Store after a network request has failed or timed out, THE Retrieval_System SHALL display a visible indication to the Staff_User that results are served from local data.
5. WHEN network connectivity is restored after an interruption, THE Retrieval_System SHALL resume serving requests that use network resources within 10 seconds of restoration without requiring the Staff_User to restart the session or re-enter the active query.

### Requirement 8: Keep the solution cost-effective

**User Story:** As an MSF program sponsor, I want a low-cost solution, so that it is affordable to deploy and maintain across field operations.

#### Acceptance Criteria

1. THE Retrieval_System SHALL operate on a single commodity device without requiring a dedicated server to serve searches to a Staff_User.
2. THE Retrieval_System SHALL perform search and retrieval without issuing any per-query paid external service call.
3. WHERE an external paid service is used during ingestion or enrichment, THE Retrieval_System SHALL store the produced index and metadata in the Local_Store so that subsequent searches incur no further external cost.
4. WHILE the Retrieval_System is in Offline_Mode, THE Retrieval_System SHALL serve search and retrieval without issuing any external service call.

### Requirement 9: Protect confidential information

**User Story:** As an MSF knowledge manager, I want documents classified by sensitivity and access controlled accordingly, so that confidential information is only shown to authorized staff.

#### Acceptance Criteria

1. THE Metadata_Component SHALL assign each Document_Record a Sensitivity_Label.
2. IF a Document_Record has no explicit Sensitivity_Label in its source metadata, THEN THE Metadata_Component SHALL assign the Sensitivity_Label the default value "public".
3. WHERE a Document has a Sensitivity_Label of "restricted", THE Search_Component SHALL exclude that Document from search results returned to a Staff_User who is not authorized for restricted documents.
4. WHEN the Search_Component returns results to a Staff_User, THE Search_Component SHALL include the Sensitivity_Label of each returned Document_Record.
5. WHILE the Retrieval_System is in Offline_Mode, THE Retrieval_System SHALL enforce the same Sensitivity_Label access rules that apply while the Retrieval_System is online.

### Requirement 10: Manage document lifecycle and identify the authoritative version

**User Story:** As a Staff_User, I want to know which version of a document is the current authoritative one, so that I act on the most correct information during a crisis.

#### Acceptance Criteria

1. THE Metadata_Component SHALL associate each Document_Record with a Document_Version.
2. WHERE two or more Document_Versions share the same logical document identity, THE Metadata_Component SHALL designate exactly one of the Document_Versions as the Authoritative_Version.
3. WHEN the Search_Component returns a Document_Record that has superseded versions, THE Search_Component SHALL indicate whether the returned Document_Version is the Authoritative_Version.
4. WHERE a Staff_User has not requested superseded versions, THE Search_Component SHALL return only the Authoritative_Version for each logical document identity.
5. WHEN the Search_Component ranks results that are otherwise equally relevant, THE Search_Component SHALL rank a Document_Record with a more recent date ahead of a Document_Record with an older date.

### Requirement 11: Support varying digital literacy and fast access

**User Story:** As a Staff_User with limited time and varying digital skills, I want a simple, fast search experience, so that I can retrieve critical information quickly during an operation.

#### Acceptance Criteria

1. WHEN a Staff_User submits a single-term query without any filter, THE Search_Component SHALL return a result set without requiring the Staff_User to configure any additional option.
2. WHEN the Search_Component returns a result, THE Search_Component SHALL present, for each result, a human-readable title or document identifier that lets the Staff_User distinguish the result from other results.
3. THE Search_Component SHALL return results for a query against a Local_Store of up to 10,000 Documents within 3 seconds.
4. WHERE a Staff_User's query returns no matches, THE Search_Component SHALL display guidance on how to broaden or change the query.

### Requirement 12: Operate within rugged, low-resource hardware constraints

**User Story:** As an MSF field IT officer, I want the system to run on limited, ruggedized field hardware and survive physical relocation, so that the system remains usable in remote low-resource settings.

#### Acceptance Criteria

1. THE Retrieval_System SHALL store the Local_Store in a single relocatable location that can be copied to another device without re-running ingestion.
2. WHEN the Retrieval_System starts against an existing Local_Store, THE Retrieval_System SHALL verify the integrity of the Local_Store and report any detected corruption.
3. IF the Local_Store is detected as corrupted on startup, THEN THE Retrieval_System SHALL report the corruption to the operator and SHALL withhold search results drawn from the corrupted data.
4. THE Retrieval_System SHALL operate using only local storage and local compute without requiring a persistent network connection.

### Requirement 13: Support long-term maintainability

**User Story:** As an MSF knowledge manager, I want the corpus and metadata to be updatable and portable over time, so that the system remains maintainable across many years and staff rotations.

#### Acceptance Criteria

1. WHEN new or updated documents and metadata are provided, THE Retrieval_System SHALL re-run ingestion and enrichment to incorporate the new or updated documents and metadata without manual modification of previously ingested records.
2. THE Metadata_Component SHALL store the Enriched_Schema in a human-readable, non-proprietary format.
3. WHEN the Enriched_Schema gains a new optional field, THE Metadata_Component SHALL continue to process existing Document_Records that lack that field without error.
4. THE Retrieval_System SHALL record the version or date of the ingestion run that produced the current Local_Store.
