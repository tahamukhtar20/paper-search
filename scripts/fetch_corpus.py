"""Download the most-cited computer science papers from OpenAlex (CC0) as JSON Lines.

Each record has the title, authors, year, citation count, a link and the abstract.

    python scripts/fetch_corpus.py --limit 10000 --out data/papers.jsonl
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.openalex.org/works"
FIELDS = "id,display_name,publication_year,cited_by_count,doi,authorships,abstract_inverted_index,primary_location"
FILTER = "primary_topic.field.id:fields/17,has_abstract:true"  # field 17 = Computer Science


def abstract(inverted: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted:
        return ""
    words = {pos: word for word, positions in inverted.items() for pos in positions}
    return " ".join(words[i] for i in sorted(words))


def link(work: dict) -> str:
    if work.get("doi"):
        return work["doi"]
    location = work.get("primary_location") or {}
    return location.get("landing_page_url") or work["id"]


def works(limit: int):
    # Plain page numbers work without an API key for the first 10,000 results.
    for page_no in range(1, min(limit, 10000) // 200 + 1):
        params = {"filter": FILTER, "sort": "cited_by_count:desc", "per_page": 200, "page": page_no, "select": FIELDS}
        req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "searchengine-demo/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            page = json.load(resp)
        if not page["results"]:
            return
        yield from page["results"]
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--out", type=Path, default=Path("data/papers.jsonl"))
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    count, seen = 0, set()
    with args.out.open("w", encoding="utf-8") as f:
        for work in works(args.limit):
            text = abstract(work.get("abstract_inverted_index"))
            title = work.get("display_name") or ""
            key = " ".join(title.lower().split())
            # OpenAlex sometimes lists one paper twice (e.g. preprint and proceedings); keep the more cited one.
            if not text or not title or key in seen:
                continue
            seen.add(key)
            record = {
                "id": work["id"].rsplit("/", 1)[-1],
                "title": work["display_name"],
                "authors": [a["author"]["display_name"] for a in work.get("authorships", [])[:8]],
                "year": work.get("publication_year"),
                "citations": work.get("cited_by_count", 0),
                "url": link(work),
                "content": text,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            if count % 1000 == 0:
                print(f"{count} papers", flush=True)
            if count >= args.limit:
                break
    print(f"Wrote {count} papers to {args.out}")


if __name__ == "__main__":
    main()
