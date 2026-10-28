"""Command-line interface: build the index, then search or serve the UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_ingestion
from .search import Filters, SearchEngine
from .store import verify_integrity

DEFAULT_CORPUS = Path("shared_documents/D4GC data/D4GC data")
DEFAULT_CSV = Path("shared_documents/documentation.csv")
DEFAULT_STORE = Path("local_store")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="msf-retrieval",
                                     description="MSF offline document retrieval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="ingest + enrich + index the corpus")
    pb.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    pb.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    pb.add_argument("--store", type=Path, default=DEFAULT_STORE)
    pb.add_argument("--limit", type=int, default=None)

    ps = sub.add_parser("search", help="run a query against the Local_Store")
    ps.add_argument("query")
    ps.add_argument("--store", type=Path, default=DEFAULT_STORE)
    ps.add_argument("--genre"); ps.add_argument("--language"); ps.add_argument("--location")
    ps.add_argument("--restricted", action="store_true", help="authorized for restricted docs")

    pv = sub.add_parser("verify", help="check Local_Store integrity")
    pv.add_argument("--store", type=Path, default=DEFAULT_STORE)

    pserve = sub.add_parser("serve", help="launch the minimal web UI")
    pserve.add_argument("--store", type=Path, default=DEFAULT_STORE)
    pserve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.cmd == "build":
        stats = run_ingestion(args.csv, args.corpus, args.store, limit=args.limit)
        print(json.dumps(stats, indent=2))
        return 0

    if args.cmd == "verify":
        res = verify_integrity(args.store)
        print(json.dumps({"ok": res.ok, "message": res.message,
                          "corrupted": res.corrupted_artifacts}, indent=2))
        return 0 if res.ok else 1

    if args.cmd == "search":
        res = verify_integrity(args.store)
        if not res.ok:
            print(f"Refusing to serve: {res.message}")
            return 1
        engine = SearchEngine(args.store, authorized_restricted=args.restricted)
        resp = engine.search(args.query, Filters(
            genre=args.genre, language=args.language, location=args.location))
        if resp.message:
            print(resp.message)
        for r in resp.results[:20]:
            flag = "" if r.is_authoritative else " (superseded)"
            print(f"[{r.id}] {r.genre} | {r.language} | {r.location} | {r.date}{flag}")
        print(f"\n{len(resp.results)} result(s), served_from_local={resp.served_from_local}")
        return 0

    if args.cmd == "serve":
        from .web import serve
        serve(args.store, args.port)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
