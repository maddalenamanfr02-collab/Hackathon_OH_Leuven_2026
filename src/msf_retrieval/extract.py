"""Text Extractor — fallback extraction from an Original_Rendering.

Used only when a document's Parsed Markdown is missing or blank. Pure stdlib:
an HTML stripper via html.parser and a lightweight PDF text-layer reader.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class ExtractResult:
    ok: bool
    text: str = ""
    failure_cause: str | None = None


class _HTMLTextParser(HTMLParser):
    _SKIP = {"script", "style", "head", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._chunks)).strip()


def extract_html(raw: str) -> str:
    parser = _HTMLTextParser()
    parser.feed(raw)
    return parser.text()


def extract_pdf(data: bytes) -> str:
    """Best-effort PDF text extraction: decode FlateDecode streams and pull
    text-show operators. Good enough for a draft; returns "" when no text layer.
    """
    chunks: list[str] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        blob = m.group(1)
        try:
            blob = zlib.decompress(blob)
        except zlib.error:
            pass
        # Text between parentheses in Tj/TJ operators.
        for t in re.finditer(rb"\((?:[^()\\]|\\.)*\)", blob):
            s = t.group(0)[1:-1]
            s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            try:
                chunks.append(s.decode("latin-1"))
            except Exception:
                continue
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()


def extract(rendering: Path) -> ExtractResult:
    try:
        suffix = rendering.suffix.lower()
        if suffix in (".html", ".htm"):
            raw = rendering.read_text(encoding="utf-8", errors="replace")
            text = extract_html(raw)
        elif suffix == ".pdf":
            text = extract_pdf(rendering.read_bytes())
        else:
            return ExtractResult(False, failure_cause=f"unsupported format {suffix}")
    except OSError as exc:
        return ExtractResult(False, failure_cause=f"read error: {exc}")

    if not text.strip():
        return ExtractResult(False, failure_cause="no extractable text layer")
    return ExtractResult(True, text=text)
