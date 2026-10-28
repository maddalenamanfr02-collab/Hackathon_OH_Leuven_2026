"""Enrichment — infer location/date/author/keywords from document text.

The draft ships a fully-offline HeuristicEnricher (zero cost, no network) so the
pipeline runs end-to-end without AWS. A BedrockEnricher stub shows where the
one-time Converse-API call would plug in (design R8.3: cache results locally).
"""
from __future__ import annotations

import re
from collections import Counter

# A small gazetteer of countries/regions MSF commonly operates in.
_LOCATIONS = [
    "Democratic Republic of the Congo", "South Sudan", "Sudan", "Yemen", "Syria",
    "Afghanistan", "Nigeria", "Ethiopia", "Somalia", "Bangladesh", "Myanmar",
    "Haiti", "Central African Republic", "Chad", "Mali", "Niger", "Iraq",
    "Lebanon", "Ukraine", "Gaza", "Palestine", "India", "Mozambique", "Kenya",
    "Uganda", "Tanzania", "Mediterranean", "Greece", "Libya", "Venezuela",
]

_DATE_RE = re.compile(r"\b(19|20)\d{2}\b")
_MONTHS = ("january february march april may june july august september "
           "october november december").split()

_STOP = set("the a an and or of to in for on with by is are was were be this that "
            "from at as it its their our we you they he she his her not no but if "
            "which who whom whose can may will shall should would could more most "
            "than then them these those into over under about after before".split())


class HeuristicEnricher:
    source = "heuristic"

    def enrich(self, doc_id: str, text: str, known: dict) -> dict:
        lowered = text.lower()
        location = next((loc for loc in _LOCATIONS if loc.lower() in lowered), "Global")

        date = ""
        years = _DATE_RE.findall(text)
        if years:
            # pick the first 4-digit year occurrence and default to Jan 01
            m = _DATE_RE.search(text)
            year = m.group(0)
            # try to find a month near it
            window = text[max(0, m.start() - 20): m.end() + 10].lower()
            month = next((i + 1 for i, name in enumerate(_MONTHS) if name in window), 1)
            date = f"{year}-{month:02d}-01"

        author = "MSF"
        keywords = [w for w, _ in Counter(
            w for w in re.findall(r"[a-zA-Z]{4,}", lowered) if w not in _STOP
        ).most_common(8)]

        return {
            "location": location,
            "date": date,
            "author": author,
            "keywords": keywords,
            "sensitivity_hint": "public",
            "_source": self.source,
        }


class BedrockEnricher:
    """One-time, cost-bounded enrichment via the Bedrock Converse API.

    Stub for the draft: wire a bedrock-runtime client here, always set
    maxTokens, use a low-cost model, and cache results in the Local_Store so
    searches never incur external cost (design R8.2/R8.3).
    """
    source = "bedrock"

    def __init__(self, client=None, model_id="amazon.nova-lite-v1:0"):
        self._client = client
        self._model_id = model_id

    def enrich(self, doc_id: str, text: str, known: dict) -> dict:  # pragma: no cover
        raise NotImplementedError("Provide a bedrock-runtime client to enable.")
