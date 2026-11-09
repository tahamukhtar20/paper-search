"""Command line: build or extend an index, search it, or export it for the web.

    python -m searchengine build data/papers.jsonl            # new index from one or more JSONL files
    python -m searchengine add more.jsonl                     # add documents to the existing index
    python -m searchengine search "neural machine translation"
    python -m searchengine export web/index                   # static files for the browser
"""

import argparse
import time
from pathlib import Path

from .export import export
from .index import InvertedIndex, read_jsonl

DEFAULT_INDEX = Path("data/index.json.gz")


def main():
    parser = argparse.ArgumentParser(prog="python -m searchengine", description="TF-IDF search engine")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help=f"index file (default {DEFAULT_INDEX})")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("build", "create a new index"), ("add", "add documents to the existing index")):
        cmd = commands.add_parser(name, help=help_text)
        cmd.add_argument("files", nargs="+", type=Path, help="JSON Lines files of documents")
    search = commands.add_parser("search", help="search the index")
    search.add_argument("query")
    search.add_argument("-k", type=int, default=10, help="number of results")
    out = commands.add_parser("export", help="write static index files for the web front end")
    out.add_argument("out", type=Path)
    out.add_argument("--corpus", default="", help="corpus description shown on the page")
    args = parser.parse_args()

    started = time.perf_counter()
    if args.command in ("build", "add"):
        index = InvertedIndex() if args.command == "build" else InvertedIndex.load(args.index)
        added = sum(index.add(read_jsonl(f)) for f in args.files)
        args.index.parent.mkdir(parents=True, exist_ok=True)
        index.save(args.index)
        print(f"Added {added} documents ({len(index)} total, {len(index.postings)} terms) in {time.perf_counter() - started:.1f}s")
    elif args.command == "search":
        index = InvertedIndex.load(args.index)
        started = time.perf_counter()
        hits = index.search(args.query, args.k)
        print(f"{len(hits)} results in {(time.perf_counter() - started) * 1000:.1f} ms")
        for rank, hit in enumerate(hits, 1):
            print(f"{rank:>2}. {hit.score:.4f}  {hit.doc['title']}  ({hit.doc.get('year', '')})")
    else:
        export(InvertedIndex.load(args.index), args.out, args.corpus)
        print(f"Exported to {args.out} in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
