"""An inverted index with TF-IDF ranking that can grow one batch of documents at a time.

The index stores raw counts (term frequency per document, document lengths), not final
scores. Scores are computed at query time, so adding documents never has to rewrite
existing entries: the document count and document frequencies simply update.

    score(d, q) = sum over unique query terms t of  tf(t, d) * idf(t)
    tf(t, d)    = count of t in d / length of d
    idf(t)      = log(N / df(t))
"""

import gzip
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .text import terms

# Titles carry more signal than body text, so title words count this many times.
TITLE_WEIGHT = 3


@dataclass
class Hit:
    doc_id: int
    score: float
    doc: dict


class InvertedIndex:
    def __init__(self):
        self.docs: list[dict] = []  # stored fields, indexed by doc id
        self.lengths: list[int] = []  # number of terms in each document
        self.postings: dict[str, dict[int, int]] = {}  # term -> {doc id: count}
        self._keys: set[str] = set()  # external ids already indexed

    def __len__(self) -> int:
        return len(self.docs)

    def add(self, documents) -> int:
        """Indexes new documents (dicts with at least 'id', 'title' and 'content'). Returns how many were added."""
        added = 0
        for doc in documents:
            if doc["id"] in self._keys:
                continue
            doc_id = len(self.docs)
            tokens = terms(doc["title"]) * TITLE_WEIGHT + terms(doc["content"])
            for term, count in Counter(tokens).items():
                self.postings.setdefault(term, {})[doc_id] = count
            self.docs.append(doc)
            self.lengths.append(len(tokens))
            self._keys.add(doc["id"])
            added += 1
        return added

    def idf(self, term: str) -> float:
        df = len(self.postings.get(term, ()))
        return math.log(len(self.docs) / df) if df else 0.0

    def search(self, query: str, k: int = 10) -> list[Hit]:
        scores: dict[int, float] = {}
        for term in set(terms(query)):
            idf = self.idf(term)
            for doc_id, count in self.postings.get(term, {}).items():
                scores[doc_id] = scores.get(doc_id, 0.0) + count / self.lengths[doc_id] * idf
        best = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        return [Hit(doc_id, score, self.docs[doc_id]) for doc_id, score in best]

    def save(self, path: Path) -> None:
        data = {
            "docs": self.docs,
            "lengths": self.lengths,
            "postings": {t: [[d, c] for d, c in p.items()] for t, p in self.postings.items()},
        }
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: Path) -> "InvertedIndex":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        index = cls()
        index.docs, index.lengths = data["docs"], data["lengths"]
        index.postings = {t: {d: c for d, c in p} for t, p in data["postings"].items()}
        index._keys = {doc["id"] for doc in index.docs}
        return index


def read_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
