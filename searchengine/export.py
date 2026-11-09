"""Writes the index as small static JSON files that a browser can search directly.

The browser only downloads what a query needs:

    manifest.json        document count, document lengths, shard counts, stop words
    forms/NN.json        word -> stem, sharded by hash of the word
    terms/NN.json        stem -> [[doc id, count], ...], sharded by hash of the stem
    docs/NNN.json        stored fields and a snippet for doc ids in blocks of DOC_BLOCK

Shards are chosen with 32-bit FNV-1a over UTF-8 bytes; web/search.js uses the same hash.
"""

import json
import shutil
from datetime import date
from pathlib import Path

from .index import InvertedIndex
from .text import STOP_WORDS, WORD, stem

SHARDS = 256
DOC_BLOCK = 50
SNIPPET_CHARS = 400


def fnv1a(text: str) -> int:
    h = 0x811C9DC5
    for byte in text.encode("utf-8"):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return h


def shard_of(key: str) -> int:
    return fnv1a(key) % SHARDS


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def export(index: InvertedIndex, out: Path, corpus: str = "") -> None:
    if out.exists():
        shutil.rmtree(out)

    # Every surface word seen in the corpus, mapped to the stem the index uses.
    forms: dict[str, str] = {}
    for doc in index.docs:
        for word in WORD.findall(f"{doc['title']} {doc['content']}".lower()):
            if word not in STOP_WORDS and word not in forms:
                forms[word] = stem(word)

    form_shards: list[dict] = [{} for _ in range(SHARDS)]
    for word, s in forms.items():
        form_shards[shard_of(word)][word] = s
    term_shards: list[dict] = [{} for _ in range(SHARDS)]
    for term, postings in index.postings.items():
        term_shards[shard_of(term)][term] = [[d, c] for d, c in postings.items()]
    for n in range(SHARDS):
        _write(out / "forms" / f"{n:02x}.json", form_shards[n])
        _write(out / "terms" / f"{n:02x}.json", term_shards[n])

    for start in range(0, len(index.docs), DOC_BLOCK):
        block = [
            {**{k: v for k, v in doc.items() if k != "content"}, "snippet": doc["content"][:SNIPPET_CHARS]}
            for doc in index.docs[start : start + DOC_BLOCK]
        ]
        _write(out / "docs" / f"{start // DOC_BLOCK:03d}.json", block)

    _write(
        out / "manifest.json",
        {
            "documents": len(index.docs),
            "terms": len(index.postings),
            "lengths": index.lengths,
            "shards": SHARDS,
            "docBlock": DOC_BLOCK,
            "stopWords": sorted(STOP_WORDS),
            "corpus": corpus,
            "built": date.today().isoformat(),
        },
    )
