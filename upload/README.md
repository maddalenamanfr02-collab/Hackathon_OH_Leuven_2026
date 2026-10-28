# upload/

Storage folder for documents uploaded through the web UI's **Import** section
(or the `--imports upload` flag of `msf-retrieval`).

- Uploaded PDF/HTML files are saved here, then ingested, enriched, and indexed
  into the Local_Store so they appear in search alongside the main corpus.
- This folder is tracked (via `.gitkeep`) so it always exists, but the uploaded
  files themselves are git-ignored — they are runtime data, not source.
