// Searches the static index written by `python -m searchengine export web/index`.
// Mirrors searchengine/index.py: score = sum over query terms of (count / doc length) * log(N / df).
// Only the shards a query touches are downloaded, and each is fetched once per visit.

const INDEX = "index";
const PAGE = 10;
const cache = new Map();

const fetchJSON = (path) => {
  if (!cache.has(path)) cache.set(path, fetch(`${INDEX}/${path}`).then((r) => (r.ok ? r.json() : {})));
  return cache.get(path);
};

// 32-bit FNV-1a over UTF-8, identical to searchengine.export.fnv1a.
// fnv1a("a") === 0xe40c292c, fnv1a("foobar") === 0xbf9cf968
function fnv1a(text) {
  let h = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(text)) h = Math.imul(h ^ byte, 0x01000193) >>> 0;
  return h >>> 0;
}

let manifest;
const shard = (key) => (fnv1a(key) % manifest.shards).toString(16).padStart(2, "0");

function queryWords(query, stopWords) {
  const words = (query.toLowerCase().match(/[a-z0-9]+/g) || []).filter((w) => !stopWords.has(w));
  return [...new Set(words)];
}

async function search(query) {
  const stopWords = new Set(manifest.stopWords);
  const words = queryWords(query, stopWords);
  const formShards = await Promise.all(words.map((w) => fetchJSON(`forms/${shard(w)}.json`)));
  const stems = [...new Set(words.map((w, i) => formShards[i][w]).filter(Boolean))];
  const termShards = await Promise.all(stems.map((s) => fetchJSON(`terms/${shard(s)}.json`)));

  const scores = new Map();
  const matched = new Map(); // doc id -> how many of the query's stems it contains
  stems.forEach((stem, i) => {
    const postings = termShards[i][stem] || [];
    const idf = Math.log(manifest.documents / postings.length);
    for (const [doc, count] of postings) {
      scores.set(doc, (scores.get(doc) || 0) + (count / manifest.lengths[doc]) * idf);
      matched.set(doc, (matched.get(doc) || 0) + 1);
    }
  });
  const ranked = [...scores].sort((a, b) => b[1] - a[1] || a[0] - b[0]);
  return { words, stems, ranked, matched };
}

const SORTS = {
  "relevance": null,
  "citations-desc": (a, b) => manifest.citations[b] - manifest.citations[a],
  "citations-asc": (a, b) => manifest.citations[a] - manifest.citations[b],
  "year-desc": (a, b) => manifest.years[b] - manifest.years[a],
  "year-asc": (a, b) => manifest.years[a] - manifest.years[b],
};

// Sorting by citations or year only considers papers containing every query term;
// otherwise a paper matching one common word could outrank the ones you meant.
// If no paper has all terms, every match is sorted. Ties keep relevance order.
function order(result, sort) {
  const compare = SORTS[sort];
  if (!compare) return { list: result.ranked, allTerms: false };
  const all = result.ranked.filter(([doc]) => result.matched.get(doc) === result.stems.length);
  const pool = all.length ? all : result.ranked;
  const rank = new Map(pool.map(([doc], i) => [doc, i]));
  const list = [...pool].sort(([a], [b]) => compare(a, b) || rank.get(a) - rank.get(b));
  return { list, allTerms: all.length > 0 };
}

async function docs(ids) {
  const blocks = await Promise.all(
    ids.map((id) => fetchJSON(`docs/${String(Math.floor(id / manifest.docBlock)).padStart(3, "0")}.json`)),
  );
  return ids.map((id, i) => blocks[i][id % manifest.docBlock]);
}

// --- rendering ---

const $ = (id) => document.getElementById(id);
const escapeHTML = (s) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const number = new Intl.NumberFormat("en");

function highlight(text, words, stems) {
  // Mark words that equal a query word or start with one of the query's stems.
  return escapeHTML(text).replace(/[A-Za-z0-9]+/g, (w) => {
    const lower = w.toLowerCase();
    return words.includes(lower) || stems.some((s) => s.length > 2 && lower.startsWith(s)) ? `<mark>${w}</mark>` : w;
  });
}

function authors(list) {
  if (!list || !list.length) return "";
  return list.length > 3 ? `${list.slice(0, 3).join(", ")} et al.` : list.join(", ");
}

let current = { list: [], shown: 0 };

async function showMore() {
  const { list: ranked, words, stems } = current;
  const slice = ranked.slice(current.shown, current.shown + PAGE);
  const found = await docs(slice.map(([id]) => id));
  const list = $("results");
  for (const doc of found) {
    const li = document.createElement("li");
    li.innerHTML = `
      <a class="title" href="${escapeHTML(doc.url)}" target="_blank" rel="noopener">${highlight(doc.title, words, stems)}</a>
      <p class="meta">${escapeHTML(authors(doc.authors))}${doc.year ? ` · ${doc.year}` : ""} · ${number.format(doc.citations)} citations</p>
      <p class="snippet">${highlight(doc.snippet, words, stems)}${doc.snippet.length >= 400 ? "…" : ""}</p>`;
    list.append(li);
  }
  current.shown += slice.length;
  $("more").hidden = current.shown >= ranked.length;
}

const SORT_LABELS = {
  "citations-desc": "most cited first",
  "citations-asc": "least cited first",
  "year-desc": "newest first",
  "year-asc": "oldest first",
};

async function run(query, sort) {
  const started = performance.now();
  const result = await search(query);
  const { list, allTerms } = order(result, sort);
  const ms = performance.now() - started;
  current = { ...result, list, shown: 0 };
  $("results").innerHTML = "";
  if (!result.words.length) {
    $("status").textContent = "";
    $("more").hidden = true;
    return;
  }
  if (!list.length) {
    $("status").textContent = `No papers match “${query}”.`;
  } else if (SORT_LABELS[sort] && allTerms && result.stems.length > 1) {
    $("status").textContent = `${number.format(list.length)} papers contain all terms, ${SORT_LABELS[sort]} (${ms.toFixed(0)} ms)`;
  } else if (SORT_LABELS[sort]) {
    $("status").textContent = `${number.format(list.length)} results, ${SORT_LABELS[sort]} (${ms.toFixed(0)} ms)`;
  } else {
    $("status").textContent = `${number.format(list.length)} results in ${ms.toFixed(0)} ms`;
  }
  await showMore();
}

async function init() {
  manifest = await fetchJSON("manifest.json");
  $("corpus").textContent = `${manifest.corpus}.`;

  const form = $("search");
  const input = $("q");
  const sort = $("sort");
  const submit = () => {
    const q = input.value.trim();
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (q && sort.value !== "relevance") params.set("sort", sort.value);
    history.replaceState(null, "", params.size ? `?${params}` : location.pathname);
    run(q, sort.value);
  };
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submit();
  });
  sort.addEventListener("change", () => input.value.trim() && submit());
  $("more").addEventListener("click", showMore);
  document.querySelectorAll("[data-example]").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      input.value = a.dataset.example;
      form.requestSubmit();
    }),
  );

  const params = new URLSearchParams(location.search);
  if (params.get("sort") in SORTS) sort.value = params.get("sort");
  const q = params.get("q");
  if (q) {
    input.value = q;
    run(q, sort.value);
  }
}

init();
