import json
import math

from searchengine.export import export, fnv1a
from searchengine.index import InvertedIndex
from searchengine.text import terms

DOCS = [
    {"id": "a", "title": "Graph search", "content": "Shortest paths in weighted graphs."},
    {"id": "b", "title": "Image models", "content": "Deep networks for image recognition."},
    {"id": "c", "title": "Searching text", "content": "Inverted indexes make text search fast."},
]


def test_terms_drop_stop_words_and_stem():
    assert terms("The Searching of the graphs") == ["search", "graph"]


def test_tf_idf_score_matches_formula():
    index = InvertedIndex()
    index.add(DOCS)
    hit = index.search("graph", k=1)[0]
    assert hit.doc["id"] == "a"
    count = index.postings["graph"][0]
    assert math.isclose(hit.score, count / index.lengths[0] * math.log(3 / 1))


def test_adding_in_batches_equals_building_at_once():
    whole = InvertedIndex()
    whole.add(DOCS)
    parts = InvertedIndex()
    parts.add(DOCS[:1])
    parts.add(DOCS[1:])
    assert [(h.doc["id"], round(h.score, 12)) for h in whole.search("search image graph")] == [
        (h.doc["id"], round(h.score, 12)) for h in parts.search("search image graph")
    ]


def test_duplicate_ids_are_skipped():
    index = InvertedIndex()
    assert index.add(DOCS) == 3
    assert index.add(DOCS[:1]) == 0
    assert len(index) == 3


def test_unknown_and_empty_queries_return_nothing():
    index = InvertedIndex()
    index.add(DOCS)
    assert index.search("zebra") == []
    assert index.search("the of and") == []


def test_save_and_load_round_trip(tmp_path):
    index = InvertedIndex()
    index.add(DOCS)
    index.save(tmp_path / "i.json.gz")
    loaded = InvertedIndex.load(tmp_path / "i.json.gz")
    assert [h.doc["id"] for h in loaded.search("text search")] == [h.doc["id"] for h in index.search("text search")]


def test_fnv1a_known_values():
    # Same vectors are checked in the browser code's comment; keeps Python and JS shards aligned.
    assert fnv1a("") == 0x811C9DC5
    assert fnv1a("a") == 0xE40C292C
    assert fnv1a("foobar") == 0xBF9CF968


def test_export_writes_shards_the_browser_can_follow(tmp_path):
    index = InvertedIndex()
    index.add(DOCS)
    export(index, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["documents"] == 3
    shard = f"{fnv1a('searching') % manifest['shards']:02x}"
    stem = json.loads((tmp_path / "forms" / f"{shard}.json").read_text())["searching"]
    postings = json.loads((tmp_path / "terms" / f"{fnv1a(stem) % manifest['shards']:02x}.json").read_text())[stem]
    assert {d for d, _ in postings} == {0, 2}
