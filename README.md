# Paper Search

A search engine over the ~10,000 most-cited computer science papers, from the 1840s to today. A Python indexer builds an inverted index with TF-IDF ranking, then exports it as small static files. The web page searches those files directly in the browser, so the whole thing is hosted as a static site with no server.

## How it works

**Indexing** (`searchengine/index.py`). Titles and abstracts are lowercased, split into words, stripped of stop words and stemmed with the Snowball stemmer. Title words count three times. The index stores raw counts: for each term, the documents that contain it and how often, plus each document's length. Scores are computed at query time, so new documents can be added at any point without rewriting existing entries.

**Ranking.** For a query, each matching document scores

```
sum over unique query terms t:  (count of t in d / length of d) * log(N / df(t))
```

where N is the number of documents and df(t) the number containing t.

Results can also be sorted by citations or by year, in either direction. Those sorts only consider papers that contain every query term (falling back to all matches if none do), so a paper that matches one common word can't jump to the top. Ties keep relevance order.

**Static export** (`searchengine/export.py`). The index is split into shards so the browser downloads only what a query needs:

| File | Contents |
|---|---|
| `manifest.json` | Document count, document lengths, years and citation counts, shard settings, stop words |
| `forms/NN.json` | Each word in the corpus mapped to its stem, sharded by hash of the word |
| `terms/NN.json` | Postings for each stem, sharded by hash of the stem |
| `docs/NNN.json` | Title, authors, year, citations, link and snippet, in blocks of 50 |

Shards are picked with 32-bit FNV-1a, implemented identically in Python and in `web/search.js`. A typical query fetches a few small shards (about 25 KB each) and ranks thousands of matches in a few tens of milliseconds.

## Running locally

Requires Python 3.10 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/fetch_corpus.py --limit 10000 --out data/papers.jsonl   # download the corpus
python -m searchengine build data/papers.jsonl                          # build the index
python -m searchengine search "shortest path algorithms"                # search from the terminal
python -m searchengine export web/index --corpus "Most-cited computer science papers"
python -m http.server 8000 -d web                                       # open http://localhost:8000
```

Add more documents to an existing index with `python -m searchengine add more.jsonl`. Input files are JSON Lines with at least `id`, `title` and `content` fields.

## Deployment

Live at [papers.tahamukhtar.com](https://papers.tahamukhtar.com). The `web/` folder, with the exported index inside, is served as static assets by Cloudflare Workers (`wrangler.jsonc`). After exporting, deploy with `npx wrangler deploy`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Data

Paper metadata and abstracts come from [OpenAlex](https://openalex.org), released under CC0. `scripts/fetch_corpus.py` takes the most-cited works whose primary field is Computer Science and that have an abstract, skipping duplicate titles.

## License

[MPL-2.0](LICENSE)
