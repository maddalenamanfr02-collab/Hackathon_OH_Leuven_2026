"""MSF Document Retrieval — offline-first, cost-effective document search.

A hackathon draft that ingests the MSF corpus (documentation.csv + Original/
renderings + Parsed Markdown), enriches metadata, builds a local SQLite+FTS5
index, and serves fast offline search with a minimal web UI.
"""

__version__ = "0.1.0"
