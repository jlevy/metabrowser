# Semantic and Hybrid CLI Search Landscape (late November 2026)

Working notes for the 2026-11-26 refresh of the 2026-05 brief. Scope: semantic and hybrid
(BM25 + vector + optional rerank) search usable from a command line, plus the model and
runtime layer underneath. Keyword-only tools are covered in a separate note.

**Conventions.** Every source was fetched on **2026-11-26** unless another date is given.
"Vendor claim" means a number published by the tool's own authors. "UNVERIFIED" means I
could not confirm the claim from a primary source. "Smoke-tested" means I ran the tool once
on a two-file Markdown corpus on the shared host (Linux x86_64, 4 vCPU, 15 GB RAM, cloud VM,
noisy); those runs check interfaces and schemas only and are **not** benchmarks. Heavy
indexing and timing belong to the benchmark agent (see `21-semantic-tools-for-benchmark.md`).

## Executive Summary

1. **The local semantic layer got cheap in 2026 because of static embeddings.**
   Model2Vec "potion"/"blink" code models (16M parameters, 256 dims, ~16 to 33 MB, no
   transformer forward pass) now drive the fastest tools: Semble, Vera's default backend,
   and zvec-grep's default. Semble reports indexing an average repo in ~207 ms and warm
   queries in ~0.7 ms on CPU with NDCG@10 0.850 on its own 1,251-query benchmark, matching a
   137M transformer (CodeRankEmbed, 0.839) that takes ~116 s to index
   ([Semble benchmarks](https://github.com/MinishLab/semble/blob/main/benchmarks/README.md),
   vendor claim). Transformer embedders on CPU remain 2 to 4 orders of magnitude slower to
   index (Vera measured Jina v5 nano on a 6-core CPU at ~3,100 chunks in ~6 minutes,
   [Vera models doc](https://github.com/VeraTools/vera/blob/master/docs/models.md)).
2. **Hybrid beats either half, and BM25 alone is a strong baseline.** In Semble's
   ablation, raw BM25 scores 0.687, raw static embeddings 0.651, fused + code-aware
   ranking 0.850. On CoIR, BM25 (42.3) still beats potion-code-16M-v2 alone (40.7) and
   loses only to the new blink-code-16M (46.8) and to transformers
   ([blink-code-16M-int8 card](https://huggingface.co/minishlab/blink-code-16M-int8)).
   Unranked ripgrep scored 0.126 on the same Semble benchmark: the gap is ranking, not
   matching.
3. **qmd (tobi/qmd) is still the leading Markdown/notes engine** (31.6k stars, v2.9.0
   2026-11-18) and remains the right first semantic-capable backend for a docs-heavy file
   browser, but only its **BM25 mode (`qmd search`)** is cheap: one SQLite FTS5 file, no
   model, ~0.16 s per CLI call on a tiny corpus here. Its hybrid `qmd query` needs ~2.25 GB
   of GGUF models (embedding 334 MB + reranker 639 MB + query-expansion 1.28 GB), a
   separate `qmd embed` pass, and seconds per query on CPU. qmd has **no path-prefix or
   explicit-file scope** in search (collections and frontmatter metadata only) and returns
   a final ranked batch, not a stream.
4. **New entrants since May 2026 that matter:** zvec-grep (`zg`, Alibaba Zvec / Qwen,
   Rust, Apache-2.0, 4.4k stars, created 2026-07-10), Semble (MinishLab, Python, MIT,
   6.5k stars), Vera v2 (VeraTools, Rust, MIT), ColGREP agent mode plus LateOn-Code
   models (LightOn), blink-code-16M (released 2026-11-24), EmbeddingGemma 2 (Apache-2.0),
   jina-embeddings-v5-text (CC-BY-NC). Fading: osgrep (no release since 2025-12-09),
   mgrep (hosted-only, last release 2026-04-25), sqlite-vss (no push since 2024-05),
   bloop (archived), jina-grep (Apple Silicon only), the old `qntx-labs/qmd` (now
   `qntx/meme`, a Rust port of qmd 2.8.3).
5. **No semantic/hybrid tool streams ranked results.** All return a final top-k batch;
   ranking needs the full candidate set. For Metabrowser's "filter a treemap/tree to
   matching files" use case, semantic search can only supply a *bounded* top-k or
   score-thresholded set; exhaustive filtering stays with ripgrep-class scanning or a BM25
   index queried with no limit.
6. **Best embeddable candidates for an optional semantic backend** (local-only, permissive
   licence, JSON output, path scoping, line ranges): **Vera** (single 134 MB binary, MIT,
   `--path` globs, `--json` with line ranges, keyword-only mode, mmap index, no daemon),
   **ck** (64 MB binary, Apache-2.0, JSONL with byte + line spans, path args, automatic
   delta indexing), **ColGREP** (168 MB binary, Apache-2.0, path args plus
   include/exclude globs, auto-incremental, late-interaction quality), **Semble**
   (Python/uv, MIT, best published quality/latency, JSON with line ranges, needs Python),
   and **qmd** for Markdown with frontmatter metadata. zvec-grep is promising but its CLI
   has **no JSON output** in v0.3.1 (MCP only).

## Master Comparison Table

Legend: L = fully local by default; K = needs API key/cloud; L/K = local default with
optional remote. Stars and dates from the GitHub API on 2026-11-26.

| Tool | Lang | Latest (date) | Licence | Local? | Retrieval | Default embedder (dims) | Index store | Machine output | Daemon / MCP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qmd (tobi/qmd) | TS (Node/Bun) | 2.9.0 (2026-11-18) | MIT | L/K | BM25, vector, hybrid RRF + LLM rerank + query expansion | embeddinggemma-300M Q8 GGUF (768) | one SQLite file (FTS5 + sqlite-vec) | JSON array, CSV, XML, MD, files | MCP stdio/HTTP, `/query` HTTP, SDK |
| zvec-grep (`zg`) | Rust (npm dist) | 0.3.1 (2026-11-16 npm) | Apache-2.0 | L/K | BM25, vector, hybrid RRF, managed rg | potion-code-16m-v2 (256) | `.zvec-grep/` (zvec) | text only (no JSON flag) | daemon on 127.0.0.1:7999, MCP |
| Semble | Python | 0.7.3 (2026-11-08) | MIT | L | BM25 + static vector, RRF + code-aware rerank | potion-code-16M-v2 in 0.7.3 (256); README on main names blink-code-16M-int8 | per-repo cache in `~/.cache/semble` | JSON (default) | MCP stdio, `--http` |
| Vera | Rust | 2.5.0 (2026-11-18) | MIT | L/K | BM25 (Tantivy) + vector, RRF, optional cross-encoder | potion-code-16M-v2 (256) | `.vera/` SQLite + Tantivy + mmap vectors | JSON | MCP stdio, `vera watch` |
| ColGREP / NextPlaid | Rust | 1.8.5 (2026-10-10) | Apache-2.0 | L | ColBERT MaxSim + SQLite FTS5 trigram, RRF | LateOn-Code-edge (17M, multi-vector 128-d/token) | PLAID index + SQLite in `~/.local/share/colgrep` | JSON | none for colgrep; NextPlaid REST server |
| ck | Rust | 0.8.1 (2026-10-11) | Apache-2.0 | L/K | regex, BM25 (Tantivy), vector, hybrid RRF, optional rerank | bge-small-en-v1.5 (384) | `.ck/` sidecars + ANN + Tantivy | JSON, JSONL | MCP (`--serve`) |
| grepai | Go | 1.2.0 (2026-10-30) | MIT | L (needs Ollama) | vector cosine (+ call graphs) | nomic-embed-text via Ollama (768) | gob file, Postgres or Qdrant | JSON, TOON | `grepai watch`, MCP |
| osgrep | TS | 0.5.16 (2025-12-09) | Apache-2.0 | L | vector + ColBERT rerank | ONNX models (~150 MB) | LanceDB | UNVERIFIED | `osgrep serve` HTTP |
| mgrep | TS | 0.1.13 (2026-04-25) | Apache-2.0 | K (Mixedbread) | hosted hybrid + rerank | hosted | Mixedbread cloud store | text | `mgrep watch` |
| semtools | Rust | 3.0.1 (2026-03-11) | MIT | L (search) | static vector cosine, line windows | potion-multilingual-128M | none, or workspace (LanceDB IVF_PQ) | JSON | none |
| probe | Rust | 0.6.0 crate; 0.6.0-rc347 npm (2026-11-11) | Apache-2.0 (npm says ISC) | L | BM25/TF-IDF + AST blocks, optional BERT rerank | none | none (no index) | JSON etc. | MCP, agent |
| Octocode | Rust | 0.30.0 (2026-11-24) | Apache-2.0 | L/K | hybrid vector + BM25, rerank, symbol graph | FastEmbed local (model UNVERIFIED) | per-project data dir | UNVERIFIED | MCP, `octocode watch` |
| codanna | Rust | 0.18.0 (2026-11-22) | Apache-2.0 | L | symbol index + semantic | fastembed (~150 MB model) | `.codanna/` (Tantivy) | JSON | MCP stdio/HTTP, `serve --watch` |
| codesearch (flupkede) | Rust | 1.8.11 (2026-11-19) | Apache-2.0 | L/K | arroy ANN + Tantivy BM25, RRF | quantized MiniLM (fastembed) | LMDB + Tantivy | MCP (compact) | multi-repo serve, REST, watch |
| cocoindex-code (`ccc`) | Python + Rust engine | 0.2.44 (2026-11-25) | Apache-2.0 | L/K | vector (AST chunks) | snowflake-arctic-embed-xs (384) | LMDB / SQLite in `.cocoindex_code/` | JSON (some commands) | auto daemon, MCP |
| SeaGOAT | Python | 1.6.1 (2026-10-25) | MIT | L | vector + ripgrep | Chroma default (all-MiniLM-L6-v2, 384) | ChromaDB | grep-line / JSON UNVERIFIED | required server |
| claude-context | TS | npm 0.1.16 (2026-11-12) | MIT | K (Milvus/Zilliz + OpenAI default) | hybrid BM25 + dense | OpenAI / Voyage / Ollama / Gemini | Milvus | MCP | MCP only |
| LEANN | Python | 0.3.9 (2026-11-02) | MIT | L | graph ANN with embedding recomputation | contriever-class (UNVERIFIED) | pruned graph (HNSW/DiskANN) | CLI, MCP | MCP |
| meme (ex qntx-labs/qmd) | Rust | 1.0.0 (2026-11-07) | MIT OR Apache-2.0 | L | qmd 2.8.3 port | as qmd (UNVERIFIED) | UNVERIFIED | UNVERIFIED | `meme-mcp` |
| `llm embed`/`similar` | Python | llm 0.38 (2026-11-17) | Apache-2.0 | L/K (plugins) | brute-force cosine | plugin-selected | SQLite `embeddings.db` | JSONL | none |
| Serena | Python | 2.1.0 (2026-10-19) | app GPL-3.0-or-later; SolidLSP MIT | L | LSP symbols + regex (no embeddings) | none | language servers | MCP | MCP |
| jina-grep | Python (MLX) | no tags; push 2026-05-13 | Apache-2.0 (models CC-BY-NC) | L, Apple Silicon only | vector rerank of grep lines | jina v5 / jina-code | none | UNVERIFIED | `serve` |

Libraries and engines (building blocks rather than end-user CLIs) are in
[Building blocks](#building-blocks-vector-stores-and-hybrid-engines).

## Capability Matrix for Metabrowser (streaming, scoping, snippets, freshness)

Metabrowser would (a) stream results, (b) filter rendered views (treemap, tree) to matching
files, (c) scope to folders/subtrees or an explicit file list, and (d) show snippets with
context. "Final batch" means results arrive only after ranking completes.

| Tool | (a) Streaming | (b) Usable as view filter | (c) Scope: path prefix / glob / explicit files / collection | (d) Snippet + location | Top-k default and cap | Freshness |
| --- | --- | --- | --- | --- | --- | --- |
| qmd | Final batch (JSON array; MCP HTTP uses SSE transport but one result) | Bounded: `--all --min-score`, or `--format files` | **No path prefix, glob or file list** in search (verified in `qmd search --help`); collections (`-c`, OR) and frontmatter metadata `--filter`; SDK same | Per document: `file` (qmd:// URI or `--full-path`), `line`, `title`, `snippet` hunk, `score`, `docid`; `qmd get file:from:count` for context | `-n` 5 (20 for json/files); `--all` | Manual `qmd update` (rescans, mtime/size state) then `qmd embed`; no watcher; optional per-collection update command |
| zvec-grep | Final batch per query group | Bounded `--limit` (default 7 per group) | `-g/--glob` include/exclude, `-t/-T` types, `--category`, `--modified-after/before`, `--symbol-type`; positional paths documented for `--rg` | `file:start-end` text previews (`--preview none/short/full/detail`) | 7 | `zg --index` incremental; `--refresh background/wait/off` (server default background); results tagged `fresh` / `possibly_stale` |
| Semble | Final JSON object | Bounded `-k` | Each positional path is indexed and searched as its own root (subtree scoping by passing the folder); `--content code/docs/config/all`; `.sembleignore` | `file_path`, `start_line`, `end_line`, `score`, `content`; `--max-snippet-lines` | `-k` 5 | mtime check on every call, incremental re-index; MCP re-indexes local paths on change |
| Vera | Final JSON array | Bounded `-n` | `--path` glob (repeatable, OR), `--lang`, `--type`, `--scope source/docs/runtime/all`, git `--changed/--since/--base` | `file_path`, `line_start`, `line_end`, `content`, `symbol_name`, `symbol_type` (no score in default JSON; smoke-tested) | `-n` 5 | `vera update .` or `vera watch .`; worktrees seed from main index |
| ColGREP | Final batch | Bounded `-k`; `-l` files only | PATH args accept files or directories; `--include`/`--exclude` globs, `--exclude-dir`, `--code-only`; `-e` regex pre-filter | `path:start-end Name`, `-n` context lines (default 6), `-c` unit code | `-k` 15 | Auto incremental update before every search |
| ck | JSONL written line by line (whether semantic results are emitted before ranking completes is UNVERIFIED; ranking implies final batch) | `--sem`/`--hybrid` bounded by `--topk` (default 10) and `--threshold` (0.6); `--regex` mode is exhaustive like grep | Path args (files or dirs), `--exclude`, `.gitignore` + `.ckignore` | JSONL `path`, `span{byte_start,byte_end,line_start,line_end}`, `language`, `snippet`, `score` (smoke-tested); `-A/-B/-C`, `--full-section` | 10 (sem) | Automatic chunk-level delta indexing (blake3) on each search; `--add` |
| grepai | Final batch | Bounded `-n` (10) | `--path` prefix filter; workspaces/projects | file, line numbers, score (help text) | 10 | `grepai watch` daemon |
| osgrep | Final batch | Bounded `-m` (25), `--per-file` | `POST /search {query, limit, path, rerank}` | snippets or `-c` chunk | 25 | `serve` watches with chokidar |
| semtools search | Final batch | `--max-distance` gives unbounded threshold set | **Explicit file list** as args or stdin | line windows `-n` (3) | `--top-k` 3 | Workspace re-embeds changed files on next search |
| `llm similar` | JSONL | Bounded `-n` UNVERIFIED | Collection only | `id`, `score`, `content`, `metadata` | UNVERIFIED | Re-run `embed-multi` (content hashes skip unchanged) |
| NextPlaid (server) | Final batch | Bounded | SQL `WHERE` metadata pre-filter | caller-defined | top_k param | Incremental add/delete |
| LanceDB (library) | Final batch | Bounded `.limit` (10) | SQL `.where()` prefilter (default) or postfilter | caller-defined | 10 | caller-managed |

Notes:

- **Streaming.** Only exhaustive scanners stream (ripgrep `--json`, ck `--regex --jsonl`,
  zg `--rg`). For ranked modes, the practical pattern is two-phase: show a fast lexical or
  filename result immediately, then replace it with the ranked semantic batch.
- **Explicit file sets.** ColGREP, ck and semtools accept file paths as arguments, so a
  selection of files can be scoped directly. Vera and zg need a glob per file. qmd cannot
  scope to files in a query; Metabrowser would have to post-filter (losing top-k
  guarantees) or create collections.
- **Subtree scope with a shared index.** Vera `--path "sub/dir/**"`, zg `-g`, ColGREP
  `--include`/PATH, grepai `--path`, ck PATH all filter one index. Semble re-roots on each
  path (a separate cached index per path).

## Per-Tool Sections

### qmd (tobi/qmd)

Sources: [README](https://github.com/tobi/qmd/blob/main/README.md),
[CHANGELOG](https://github.com/tobi/qmd/blob/main/CHANGELOG.md),
[npm @tobilu/qmd](https://registry.npmjs.org/@tobilu/qmd), GitHub API.

- **State:** TypeScript, runs on Node >= 22 or Bun; npm `@tobilu/qmd` 2.9.0 (2026-11-18;
  CHANGELOG dates it 2026-11-17); 31,610 stars; MIT; last push 2026-11-20. Releases since
  the 2026-05 brief: 2.5.x (May), 2.6.3 (2026-06-24), 2.8.3 (2026-08-16), 2.9.0.
- **Modes:** `qmd search` (BM25 via SQLite FTS5, `porter unicode61` tokenizer), `qmd
  vsearch` (vector only), `qmd query` (hybrid). Query pipeline: fine-tuned 1.7B
  query-expansion model produces typed `lex`/`vec`/`hyde` sub-queries; original query
  weighted x2; each sub-query hits FTS and vector; RRF with k=60 plus top-rank bonus; top
  30 to 40 candidates reranked by Qwen3-Reranker-0.6B (yes/no logprobs); position-aware
  blend of RRF and reranker scores. Typed query documents (`lex:`, `vec:`, `hyde:`) skip
  expansion; `--no-rerank` gives RRF only.
- **Models (auto-downloaded to `~/.cache/qmd/models/`):** `embeddinggemma-300M-Q8_0`
  (333.6 MB), `qwen3-reranker-0.6b-q8_0` (639.2 MB), `qmd-query-expansion-1.7B-q4_k_m`
  (1,282.4 MB); sizes from the Hugging Face file listings. Total ~2.25 GB. Override
  embedder with `QMD_EMBED_MODEL` (Qwen3-Embedding-0.6B GGUF suggested for CJK). Since
  2.9.0 an OpenAI-compatible remote embedder can be configured (`models.embed:
  "http://host/v1#model"`), but expansion and reranking stay local.
- **Chunking:** 900 tokens per chunk, 15% overlap (regex); `--chunk-strategy auto` adds
  tree-sitter AST chunking for TS, JS, Python, Go, Rust. Markdown is always regex-chunked.
- **Index format:** one SQLite file per named index (`~/.cache/qmd/<index>.sqlite`) with
  `documents`, `documents_fts` (FTS5), `content`, `content_vectors`, `vector_rows`,
  `file_sync_state`, metadata tables. Directly readable with `sqlite3` (schema listed in a
  smoke test of 2.9.0). The 2026-05 brief measured ~26 MB of index for an 11.4 MB,
  310-file corpus (BM25 only).
- **Interfaces:** `--format json|csv|md|xml|files|cli`, `--explain` score traces, `qmd
  get file:from:count`, `multi-get`. JSON (smoke-tested): array of
  `{docid, score, file, line, title, snippet}`. MCP tools `query`, `get`, `multi_get`,
  `status`, `metadata`; `qmd mcp --http [--daemon]` serves `POST /mcp`, `POST /query`
  (alias `/search`), `POST /metadata`, `GET /health` on localhost:8181 with Origin/Host
  checks. SDK `createStore({dbPath, config})` with `search`, `searchLex`, `searchVector`,
  `update`, `embed`, AbortSignal support for remote embeddings.
- **Performance:** Smoke test here: `qmd search` on a 2-file corpus takes 0.16 s wall per
  CLI call (Node startup dominated). 2026-05 brief: ~240 ms per BM25 query over 310
  files (1.197 s for five queries). 2.9.0 claims keyword search ~12x faster over 13
  collections by running one FTS query instead of one per collection (CHANGELOG).
  0.9.0 notes said HTTP daemon mode "cuts warm query latency from ~16s to ~10s" for
  `query` (hardware unstated). Qwen3-Embedding-0.6B costs ~1,190 MB per 2,048-token
  context (CHANGELOG). CPU embedding throughput for embeddinggemma: UNVERIFIED (no
  published number found).
- **Concurrency/safety:** 2.9.0 serializes embeds with a per-index lock; the 2026-05 brief
  saw `database is locked` under parallel CLI calls. 2.8.3 added a trust gate: a
  project-local `.qmd/index.yml` can define shell `update:` commands and model URIs, which
  now require `qmd trust` approval. A file browser embedding qmd should use explicit
  `dbPath`/`--index` and never adopt a browsed tree's `.qmd` config.
- **Freshness:** `qmd update` rescans (mtime/size table), then `qmd embed`. No watcher.
- **Suitability:** Good optional backend for Markdown/notes (titles, contexts, frontmatter
  metadata filters, docids, line-anchored snippets). Weak fit for (b)/(c): no path or
  file-set scoping, ranked batch only. BM25 mode is cheap; hybrid mode carries a 2.25 GB
  model download and multi-second CPU queries unless a daemon keeps models loaded.

### qmd vs ripgrep-class search as a Metabrowser backend

| Question | ripgrep (`rg --json`) | `qmd search` (BM25) | `qmd query` (hybrid) |
| --- | --- | --- | --- |
| Setup | none | `collection add` + `update` (index ~2.3x corpus for Markdown, per the 2026-05 brief) | plus `qmd embed` and ~2.25 GB of models |
| Matching | exhaustive regex/literal, every occurrence with byte offsets | tokenised terms, porter stemming, per-document best snippet | adds paraphrase and concept matches |
| Ranking | none (walk order) | BM25 with title/path fields | RRF + LLM rerank |
| Output | streaming JSON lines per match | final top-N array per document | final top-N array |
| Scoping | any paths, globs, file lists | collections, metadata only | same |
| Latency (small corpora) | tens of ms per query (2026-05 brief: ~17 ms per query, 310 files) | ~0.16 s per CLI call minimum (Node); ~240 ms per query in the 2026-05 brief | seconds on CPU; daemon recommended |
| Freshness | always current | stale until `qmd update` | stale until `update` + `embed` |

When BM25/hybrid ranking beats unranked regex scanning:

- **Multi-word, natural-language, topic queries over prose** (for example "process pool memory pressure and status events"). The 2026-05 benchmark on a private 310-file Markdown corpus put the
  known target at rank 1 for 5/5 queries with `qmd search`; ripgrep's walk order put one
  target at rank 26 of 26. Semble's code benchmark shows the same shape: ripgrep NDCG@10
  0.126 vs plain BM25 0.673 (vendor benchmark; ripgrep was given split keywords).
- **When results feed a bounded list** (palette, agent context). Ranked top-10 is useful;
  hundreds of unranked hits are not.

When ripgrep wins:

- Exact identifiers, error strings, regexes, counts, "every occurrence" queries.
- **View filtering** (treemap, tree): needs the complete matching file set, streamed, with
  arbitrary path scoping. That is ripgrep's natural output (`rg -l`, `rg --json`) and not
  what a top-k ranker returns.
- Freshness-critical views (no index to go stale) and zero-setup roots.

Cost of adding BM25 ranking without qmd: a BM25 index is cheap (Semble's BM25 baseline
indexes an average benchmark repo in 47 ms and answers in 0.17 ms; Tantivy and SQLite FTS5
are embeddable). The expensive part of qmd is the LLM layer, not BM25. A reasonable
Metabrowser design is: ripgrep for exhaustive/streamed/filter results; an optional ranked
provider (qmd BM25, or an embedded FTS index) for "find docs about X"; semantic/hybrid as
an opt-in provider behind the same contract.

### zvec-grep (`zg`)

Sources: [README](https://github.com/zvec-ai/zvec-grep),
[docs](https://zvec.org/en/docs/zvec-grep/) (CLI, search, indexing, embedding-models,
server pages), [Alibaba Cloud blog "From rg to zg"](https://www.alibabacloud.com/blog/from-rg-to-zg-local-search-beyond-keywords_603530),
[MarkTechPost 2026-09-02](https://www.marktechpost.com/2026/09/02/qwen-developers-open-sources-zg-zvec-grep-a-local-first-search-layer-unifying-ripgrep-bm25-and-vector-search/),
npm `@zvec/zvec-grep`. Smoke-tested `zg --help search` for 0.3.1.

- Rust core distributed through npm (Node >= 22); repo created 2026-07-10, 4,381 stars,
  Apache-2.0, release v0.3.1 (GitHub 2026-11-18, npm 2026-11-16). Built on Alibaba's
  `zvec` vector database. The installed package is 136 MB.
- Modes: hybrid (default for positional words), `--fts` (BM25), `--vector`, `--fuse` to
  merge groups, `--rg` exhaustive managed ripgrep (embedded Rust regex engine; no PCRE2).
  RRF fusion per third-party coverage; reranker UNVERIFIED.
- Local embedders (docs): `local/potion-code-16m-v2` (default, Model2Vec FP16),
  potion-retrieval-32m, potion-multilingual-128m, all-MiniLM-L6-v2 / bge-small /
  multilingual-e5-small / jina-embeddings-v2-base-code / gte-modernbert-base /
  nomic-embed-text-v1.5 (ONNX), embeddinggemma-300m and qwen3-embedding-0.6b (GGUF).
  Remote: Qwen text-embedding-v4, qwen3.7-text-embedding, qwen3-vl-embedding.
- Index under `<root>/.zvec-grep/`; `zg --index` incremental; model change needs
  `--rebuild`. Non-interactive searches never create an index.
- Daemon: `zg --server on|run|off|status`, loopback 127.0.0.1:7999, optional bearer token;
  `zg --server --stdio` proxies MCP; CLI `--mode direct|server|auto`.
- **No JSON/JSONL CLI output** in 0.3.1 (help text has none); machine access is via MCP.
- Quality: Semble's benchmark scored zvec-grep 0.670 NDCG@10, 3.4 s index, 391 ms query
  (direct mode). zg's own benchmarks are agent A/B studies with remote Qwen3.7 embeddings.
- Suitability: strong design (rg + BM25 + vector in one binary, freshness flags), but
  text-only CLI output makes it a poor subprocess backend today; revisit when JSON lands.

### Semble (MinishLab)

Sources: [README](https://github.com/MinishLab/semble),
[benchmarks](https://github.com/MinishLab/semble/blob/main/benchmarks/README.md), PyPI
`semble` 0.7.3 (2026-11-08). Smoke-tested 0.7.3.

- Python (uv tool), MIT, 6,495 stars, created 2026-04-06, active.
- Pipeline: tree-sitter code chunks; BM25 + Model2Vec static embeddings fused with RRF;
  code-aware reranking (adaptive lexical weight for symbol-like queries, definition
  boosts, identifier stems, file coherence, test/legacy penalties). README on `main` names
  `blink-code-16M-int8`; the 0.7.3 install here downloaded `potion-code-16M-v2`
  (33 MB in the HF cache).
- Interfaces: `semble search QUERY [path|git-url ...] -k --format json|text --content
  code|docs|config|all --max-snippet-lines N`; `find-related file line`; Python
  `SembleIndex.from_path(...).search()`; MCP (`search`, `find_related`), `semble --http`.
  JSON (smoke-tested): `{query, results:[{file_path,start_line,end_line,score,content}]}`.
- Performance (vendor): index ~207 ms average repo, query p50 0.73 ms in-process; 1 MB
  per-file cap (`SEMBLE_MAX_FILE_BYTES`); 4 worker processes for chunking. Smoke test
  here: first call 4.1 s including model download; warm CLI calls 0.68 to 0.73 s and
  ~150 MB max RSS on a 2-file corpus (Python start-up dominates).
- Index size: Vera's comparison measured Semble's caches at 32 GB across 63 repositories
  vs 4.7 GB for Vera (Vera vendor doc; Semble 0.5.5).
- Suitability: best published quality/latency; JSON with line ranges; but per-call Python
  start-up (~0.7 s) means a long-lived `--http`/MCP process is needed for interactive use.

### Vera (VeraTools, formerly lemon07r/Vera)

Sources: [README](https://github.com/VeraTools/vera),
[models](https://github.com/VeraTools/vera/blob/master/docs/models.md),
[benchmarks](https://github.com/VeraTools/vera/blob/master/docs/benchmarks.md). Smoke-tested
2.5.0 (keyword-only index).

- Rust, MIT, 153 stars, v2.5.0 (2026-11-18); single 134 MB Linux binary; npm
  `@vera-ai/cli` and PyPI `vera-ai` are installers. Daily GitHub update check
  (`VERA_NO_UPDATE_CHECK=1`).
- Pipeline: tree-sitter symbol chunks (54 of 65 languages), Markdown sections; BM25
  (Tantivy) + vector, rank fusion, optional cross-encoder, code-aware priors. Store:
  `.vera/` with SQLite metadata, Tantivy, memory-mapped vectors. Default embedder
  potion-code-16M-v2 (~32 MB download). Optional local Jina v5 nano / CodeRankEmbed ONNX,
  or API mode (Qwen3-Embedding-8B + Qwen3-Reranker-8B). `--full-text-only` index needs no
  model.
- Interfaces: `vera search` with `--json`, `--limit`, `--path` (glob, repeatable),
  `--lang`, `--type`, `--scope`, `--changed`, `--since`, `--base`, `--also` (other
  indexed repos), `--compact`, `--timing`; `vera grep`, `vera structural ...`,
  `vera references`; MCP stdio with seven tools. JSON (smoke-tested): array of
  `{file_path,line_start,line_end,content,symbol_name,symbol_type}`.
- Performance (vendor, Ryzen 7 9800X3D): Vera repo 447 files / 8,109 chunks indexed in
  0.9 s; Flask 227 files in 0.3 s; full Semble suite 89 s; CLI search ~0.13 s including
  process start; Jina ONNX on a 6-core CPU ~3,100 chunks in ~6 minutes. Local rerankers
  did not beat no-rerank in their screening (0.8540 vs 0.8497 best).
- Quality (vendor): 0.8436 NDCG@10 on the 1,251-task Semble suite (Vera 2.0.1) vs Semble
  0.5.5 at 0.8514.
- Suitability: the strongest single-binary, no-daemon, JSON + path-glob candidate.

### ColGREP / NextPlaid (LightOn)

Sources: [repo README](https://github.com/lightonai/next-plaid),
[colgrep README](https://github.com/lightonai/next-plaid/blob/main/colgrep/README.md),
[LateOn-Code-edge card](https://huggingface.co/lightonai/LateOn-Code-edge).

- Rust, Apache-2.0, v1.8.5 (2026-10-10), 624 stars; 168 MB Linux binary (bundles ONNX
  Runtime).
- Pipeline: tree-sitter code units rendered as structured text (signature, params, calls,
  docstring); LateOn-Code-edge (17M parameters, ColBERT multi-vector, ~300 x 128-d vectors
  per unit) with PLAID index (2- or 4-bit residual quantization, mmap), optional 1-bit
  binary storage and pooling; fused with SQLite FTS5 trigram keyword search by RRF
  (`--alpha` 0.60 default; `--semantic-only`). INT8 ONNX model is 17.2 MB; FP32 68 MB.
- Interfaces: `colgrep [QUERY] [PATH...]`, `-k` (15), `-n` context (6), `-l`, `-c`,
  `--json`, `--include/--exclude/--exclude-dir`, `-e` regex pre-filter, `--code-only`.
  Index in `~/.local/share/colgrep/indices/`; auto-incremental on each search.
- Agent mode: `colgrep --agent` runs a local 2B search model (2.5 GB download), ~75 to
  90 s per question on CPU only (vendor, M3 Pro).
- NextPlaid server: REST API, metadata SQL pre-filters, CPU QPS ~17 with P95 220 to
  455 ms on BEIR datasets (INT8 ONNX encoding, vendor).
- Quality conflict: ColGREP claims 0.846 NDCG@10 (LateOn-Code-edge) and 0.859
  (LateOn-Code) on Semble's benchmark **on an H100 at FP32**; Semble's own run scored
  ColGREP 0.693 (5.4 s index, 122 ms query, CPU). Treat both as vendor numbers; the
  CPU/INT8 configuration is the one relevant here.

### ck (BeaconBay)

Sources: [README](https://github.com/BeaconBay/ck), crates.io `ck-search` 0.8.1. Smoke-tested
0.8.1 (`--regex` and `--lex` JSONL).

- Rust, Apache-2.0, 1,771 stars, 0.8.1 (2026-10-11); 64 MB binary.
- Modes: `--regex` (default, grep-compatible, no index), `--lex` (Tantivy BM25), `--sem`,
  `--hybrid` (RRF), `--rerank`. Models via FastEmbed: `bge-small` default (384-d,
  400-token chunks), `mxbai-xsmall`, `nomic-v1.5`, `jina-code`.
- Index: `.ck/` beside the code or under `CK_INDEX_DIR` (per-file `.ck` sidecars,
  `manifest.json`, `tantivy_index/`, ANN file); "~2x source size" (vendor). Chunk-level
  delta re-embedding keyed by blake3.
- JSONL (smoke-tested): `{"path","span":{"byte_start","byte_end","line_start","line_end"},
  "language","snippet","score"}`. Best location data of the semantic tools.
- Performance: vendor "~1M LOC in under 2 minutes", sub-500 ms queries; Semble measured
  ck at 96 s index, 187 ms query, 0.642 NDCG@10.
- Suitability: good contract (JSONL, byte offsets, path args, grep-compatible flags), but
  transformer embedding makes first index slow on 4 vCPU.

### grepai

Sources: [README](https://github.com/yoanbernabeu/grepai), [docs](https://yoanbernabeu.github.io/grepai/),
`grepai search --help` (1.2.0).

- GitHub reports language C, the README and binary are Go; MIT; v1.2.0 (2026-10-30); 25 MB
  binary. Contributions are issue-first; PRs not accepted.
- Requires an embedding provider: Ollama (default, `nomic-embed-text`), LM Studio,
  OpenAI, OpenRouter, Requesty. Storage: gob file, Postgres or Qdrant. `grepai watch`
  daemon keeps the index fresh. `search --json|--toon`, `--limit` (10), `--path` prefix.
- Semble measured 0.561 NDCG@10, 35 s index, 48 ms query.
- Suitability: Ollama dependency and pure-vector ranking make it a weaker default.

### Other code-semantic tools (brief)

- **osgrep** ([repo](https://github.com/Ryandonofrio3/osgrep)): ONNX local embeddings
  (~150 MB), LanceDB, ColBERT rerank, `serve` HTTP with watch. No release since
  2025-12-09; last push 2026-01-17. Watchlist / stale.
- **mgrep** ([repo](https://github.com/mixedbread-ai/mgrep)): requires Mixedbread login or
  `MXBAI_API_KEY`; files sync to a hosted store via `mgrep watch`; 1 MB/1,000-file
  default limits; vendor claims 2x fewer agent tokens. Not local; community forks claim
  Ollama-based local modes (UNVERIFIED).
- **probe** ([repo](https://github.com/probelabs/probe)): no embeddings; BM25/TF-IDF over
  tree-sitter blocks with Elasticsearch-style boolean queries, optional BERT rerank,
  `--max-tokens`; MCP and agent modes. crates `probe-code` 0.6.0; npm still on
  `0.6.0-rc347` (2026-11-11). Semble measured 0.387 NDCG@10 for `probe search`.
- **Octocode** ([repo](https://github.com/Muvon/octocode)): Rust, Apache-2.0, 0.30.0
  (2026-11-24); local FastEmbed embedding and reranking by default; MCP; its June 2026
  benchmark showed hybrid weighted toward keywords (0.3/0.7) beating dense-only (NDCG@10
  0.620 vs 0.528).
- **codanna** ([repo](https://github.com/bartolli/codanna)): Rust symbol/call-graph index
  plus semantic search; ~150 MB model; warm lookups under 10 ms (vendor); MCP `serve
  --watch`; `--json`.
- **codesearch (flupkede)** ([repo](https://github.com/flupkede/codesearch)): Rust MCP
  server, arroy ANN in LMDB + Tantivy BM25 + RRF, multi-repo fan-out, REST, watch; ONNX
  build needs AVX2.
- **cocoindex-code (`ccc`)** ([repo](https://github.com/cocoindex-io/cocoindex-code)):
  Python CLI on a Rust engine; local default `Snowflake/snowflake-arctic-embed-xs` with
  `[full]` extra (~1 GB torch); auto-started daemon; `--path`, `--lang`,
  `--offset/--limit`, `--refresh`; LMDB index with a 4 GiB default ceiling.
- **SeaGOAT** ([repo](https://github.com/kantord/SeaGOAT)): Python, ChromaDB with
  Chroma's default embedder, requires `seagoat-server`; active (1.6.1).
- **claude-context** ([repo](https://github.com/zilliztech/claude-context)): MCP only;
  needs Milvus/Zilliz plus an embedding API by default (OpenAI, Voyage, Gemini or
  Ollama); hybrid BM25 + dense; Merkle-tree incremental indexing. Not a local CLI.
- **LEANN** ([repo](https://github.com/StarTrail-org/LEANN)): storage-light ANN that
  recomputes embeddings at query time ("97% less storage"; vendor); MCP; DiskANN extra.
  Interesting for huge personal corpora, slow-query trade-off.
- **semtools** ([repo](https://github.com/run-llama/semtools)): `semtools search QUERY
  FILES...` with potion-multilingual-128M; explicit file lists, line windows, `--json`;
  `parse` needs LlamaParse API; last release 2026-03-11.
- **Serena** ([repo](https://github.com/oraios/serena)): LSP-backed symbol tools over MCP,
  no embeddings. **Licence changed:** the Serena application is now GPL-3.0-or-later and
  SolidLSP MIT (LICENSE file; PyPI `serena-agent` 2.1.0). The 2026-05 brief did not cover
  it; flag the GPL for any embedding.
- **Sourcebot** ([repo](https://github.com/sourcebot-dev/sourcebot)): self-hosted
  (Docker) code search (regex/boolean, Zoekt-class) with MCP and an LLM "Ask" feature;
  not embedding search. v6.1.2 (2026-11-25).
- **Sourcegraph:** `src-cli` 8.2.0 (2026-11-11). Deep Search is an async API on Sourcegraph
  7.x, only with the Sourcegraph model provider
  ([docs](https://sourcegraph.com/docs/deep-search/api)); no `src` Deep Search subcommand
  found. The `sourcegraph/cody` GitHub repo returns 404 (reason UNVERIFIED).
- **Greptile:** `greptileai/cli` (2026-05-22, 12 stars, no licence) is a code-review CLI
  for the hosted service, not local search.
- **Continue / Cursor:** Continue's `@codebase` embeddings index (transformers.js,
  `~/.continue/index`) is marked deprecated in its docs
  ([page](https://docs.continue.dev/reference/deprecated-codebase)); the `cn` CLI docs do
  not mention indexing. Cursor's index is server-side; no local CLI exposure found
  (UNVERIFIED).
- **bloop:** archived (GitHub `archived: true`, last push 2024-12-04).
- **jina-grep** ([repo](https://github.com/jina-ai/jina-grep-cli)): MLX, Apple Silicon
  only; pipe mode reranks grep output; ~10 ms/query with its server (vendor). Not usable
  on Linux.
- **Watchlist (low adoption):** `ogrep` (PyPI 0.12.0, 2026-05-03, no release since),
  `ripvec` (crate 4.1.15, 2026-06-04), `vecgrep` (martintrojer, crate 0.10.0, 2026-04-03),
  `vecgrep` (Go, Ollama + sqlite-vec), `omengrep` (under rewrite), `semble_rs` (no
  licence), `embgrep`, `skylakegrep` (Ollama), `cqs` (crate), codebase-memory-mcp,
  GitNexus, codegraph (the last three appear in Semble's excluded/compared lists).

### General-purpose embedding CLIs

- **`llm embed` / `embed-multi` / `similar`** ([docs](https://llm.datasette.io/en/stable/embeddings/cli.html)):
  `embed-multi --files DIR '**/*.md' --store` writes to SQLite `embeddings.db`;
  `llm similar COLLECTION -c TEXT` prints JSONL `{id, score, content, metadata}`. Search
  is brute-force cosine; the docs say it "does not scale well to large collections".
  Embedding models come from plugins (e.g. `llm-sentence-transformers` 0.3.2, last
  release 2025-04).
- **txtai** 9.15.0 ([repo](https://github.com/neuml/txtai)): Python embeddings database
  combining sparse and dense indexes, graph and relational storage; FastAPI and MCP APIs.
  A framework, not a grep-like CLI.
- **Ollama-backed tools:** grepai, vecgrep (Go), skylakegrep, SeaGOAT's generative mode,
  claude-context's Ollama option. All require a running Ollama daemon; embedding
  throughput is Ollama's (llama.cpp) CPU throughput.

## Building Blocks: Vector Stores and Hybrid Engines

| Component | Version (date) | Licence | Notes |
| --- | --- | --- | --- |
| sqlite-vec | 0.1.10-alpha.4 (2026-05-18); npm/PyPI 0.1.9 (2026-03-31) | MIT/Apache-2.0 | `vec0` virtual tables, float/int8/binary vectors, metadata and partition columns; brute-force KNN; qmd uses it. No release since May. |
| sqlite-vss | last push 2024-05-05 | MIT | Inactive; use sqlite-vec. |
| SQLite FTS5 | (SQLite) | public domain | qmd's BM25; ColGREP uses a trigram FTS5 table. |
| Tantivy | crate 0.27.0 (2026-10-17); GitHub release 0.26.1 | MIT | BM25 in ck, Vera, codesearch, codanna. |
| LanceDB | crate/PyPI/npm 0.41.0 (2026-10-29); GitHub 0.42.0-beta.33 | Apache-2.0 | Embedded; hybrid with RRF default reranker, SQL `where` prefilter, default limit 10 ([docs](https://docs.lancedb.com/search/hybrid-search)). Used by osgrep, semtools workspaces. |
| Meilisearch | v1.58.0 (2026-11-23) | GitHub shows NOASSERTION (MIT core plus enterprise terms, UNVERIFIED) | Server; hybrid via configured embedders and `semanticRatio` ([docs](https://www.meilisearch.com/docs/learn/ai_powered_search/getting_started_with_ai_search)). |
| Typesense | v30.2 (2026-04-19) | GPL-3.0 | Server; GPL. |
| Chroma | GitHub push 2026-11-20; PyPI 1.5.9 (2026-05-05); `cli-1.4.4` | Apache-2.0 | Server/embedded; SeaGOAT uses it. |
| Turbopuffer | hosted | client MIT | Cloud only. |
| zvec | (powers zg) | UNVERIFIED | `alibaba/zvec` linked from zg README; the `zvec-ai/zvec` path 404s. |
| NextPlaid | 1.8.5 | Apache-2.0 | Multi-vector (ColBERT) DB, REST, SQL pre-filter. |

## Model Layer

### Embedding models relevant to local CPU search

| Model | Params | Dims | Type | Licence | Evidence |
| --- | --- | --- | --- | --- | --- |
| blink-code-16M(-int8) | 16.0M | 256 | static (Model2Vec) | MIT | CoIR 46.82, RTEB(Code) 34.67; + BM25 hybrid CoIR 49.36; int8 = 16 MB; HF repo created 2026-11-24 ([card](https://huggingface.co/minishlab/blink-code-16M-int8)) |
| potion-code-16M-v2 | 16.2M | 256 | static, distilled from CodeRankEmbed | MIT | CoIR 39.08 (512-token cap) / 40.67; 32.5 MB safetensors ([card](https://huggingface.co/minishlab/potion-code-16M-v2)) |
| potion-retrieval-32M / potion-multilingual-128M | 32M / 128M | 256 | static | MIT | used by zg, semtools |
| LateOn-Code-edge | 17M | 128 per token | ColBERT multi-vector | Apache-2.0 | MTEB(Code v1) avg 66.64 (fine-tuned on CoIR training data); INT8 ONNX 17.2 MB ([card](https://huggingface.co/lightonai/LateOn-Code-edge)) |
| LateOn-Code | 149M | 128 per token | ColBERT | Apache-2.0 | MTEB(Code v1) 74.12 (same card) |
| mxbai-edge-colbert-v0-17m / -32m | 17M / 32M | multi-vector | ColBERT | Apache-2.0 | text retrieval; ONNX variants for NextPlaid |
| answerai-colbert-small-v1 | 33M | multi-vector | ColBERT | MIT | NextPlaid lightweight text default |
| bge-small-en-v1.5 | 33M | 384 | transformer | MIT | ck and fastembed-rs default; quantized ONNX 66.5 MB |
| snowflake-arctic-embed-xs | 22.6M | 384 | transformer | (card) | cocoindex-code default |
| all-MiniLM-L6-v2 | 22M | 384 | transformer | Apache-2.0 | Chroma/SeaGOAT, codesearch quantized default |
| granite-embedding-small-english-r2 | 47.7M | 384 | transformer | Apache-2.0 | MTEB(Code v1) 55.84 (LateOn card) |
| nomic-embed-text-v1.5 | 137M | 768 (MRL) | transformer | Apache-2.0 | grepai/Ollama default |
| CodeRankEmbed | 137M | 768 | transformer | MIT | MTEB(Code v1) 60.47; Semble bench 0.839 but 116 s index |
| jina-embeddings-v2-base-code | 161M | 768 | transformer | Apache-2.0 | zg/ck option |
| EmbeddingGemma-300m | 308M | 768 (MRL 512/256/128) | transformer | Gemma terms | <200 MB RAM quantized, 2K context, "<15 ms for 256 tokens on EdgeTPU" ([Google blog](https://developers.googleblog.com/en/introducing-embeddinggemma/)); MTEB(Code v1) 68.76 (LateOn card); Q8 GGUF 333.6 MB; qmd default |
| EmbeddingGemma 2 | 740M multimodal; 270M text/code base | 768 (MRL) | transformer | Apache-2.0 | 8,192-token text context ([gemma.ai](https://gemma.ai/models/embeddinggemma/)); HF repo `google/embeddinggemma-2` created 2026-09-14; CPU numbers UNVERIFIED |
| Qwen3-Embedding-0.6B / 4B / 8B | 0.6B / 4B / 8B | up to 1024 / 2560 / 4096 (MRL 32+) | transformer | Apache-2.0 | 32K context; MTEB(Code v1) 75.42 for 0.6B ([card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)); ~1.19 GB per 2,048-token llama.cpp context (qmd CHANGELOG) |
| jina-embeddings-v5-text-nano / small | 239M / 677M | 768 / 1024 (MRL) | transformer | **CC-BY-NC-4.0** | released 2026-02-18; MTEB English v2 71.0 (nano) ([card](https://huggingface.co/jinaai/jina-embeddings-v5-text-nano)) |
| jina-code-embeddings-0.5b / 1.5b | 0.49B / 1.54B | 896 / 1536 | transformer | **CC-BY-NC-4.0** | code tasks; non-commercial licence |

### Rerankers

- **Qwen3-Reranker-0.6B** (Apache-2.0; Q8 GGUF 639 MB): qmd's local reranker.
- **jina-reranker-v2-base-multilingual**, **mxbai-rerank-xsmall-v1**,
  **gte-reranker-modernbert-base**, **bge-reranker-base / v2-m3** (fastembed-rs list).
- Evidence that local cross-encoders may not help code search: Vera's 2026-08-23
  screening found no local reranker beating no-rerank (0.8540 baseline vs 0.8497 best);
  only the API Qwen3-Reranker-8B helped (0.8647). Semble and Vera rely on cheap
  code-aware heuristics instead.

### Runtimes

| Runtime | Version (date) | Used by |
| --- | --- | --- |
| llama.cpp (GGUF) | b12753 (2026-11-26) | qmd via node-llama-cpp 3.22.4 (2026-11-25); zg GGUF models; ColGREP agent |
| ONNX Runtime | PyPI 1.32.0 (2026-11-13); Rust `ort` 2.0.0-rc.15 | fastembed, ck, Vera ONNX, ColGREP, codesearch, osgrep |
| fastembed (Python) / fastembed-rs | 0.9.1 (2026-10-24) / 7.8.0 (2026-11-22) | ck, Octocode, codanna, codesearch; fastembed-rs default bge-small-en-v1.5; Qwen3 via candle feature |
| candle | candle-core 0.11.1 (2026-10-31) | fastembed-rs Qwen3/nomic-v2 backends |
| Model2Vec / model2vec-rs | 0.10.0 (2026-10-11) / 0.5.1 (2026-11-24) | Semble, Vera, zg, semtools (static embeddings, "up to 30000x faster on CPU", vendor) |
| transformers.js | 4.3.2 (2026-10-28) | Continue's deprecated index; browser-side option |
| sentence-transformers | 6.3.0 (2026-11-11) | cocoindex-code `[full]`, Python tools |

### CPU throughput, index bytes and latency (published numbers)

| Configuration | Number | Source |
| --- | --- | --- |
| potion-code-16M-v2 (Vera, Ryzen 7 9800X3D) | 8,109 chunks indexed in 0.9 s (~9,000 chunks/s incl. parsing) | Vera models doc |
| Jina v5 nano ONNX on 6-core CPU (Vera) | ~3,100 chunks in ~6 min (~9 chunks/s) | Vera models doc |
| Semble (static) vs CodeRankEmbed 137M | index 207 ms vs 116 s per average repo; query 0.73 ms vs 16 ms | Semble benchmarks (hardware unstated, CPU) |
| ck (bge-small), grepai (nomic via Ollama), ColGREP, zg | index 96 s / 35 s / 5.4 s / 3.4 s; query 187 / 48 / 122 / 391 ms | Semble benchmarks |
| NextPlaid INT8 ONNX encoding, CPU | ~17 QPS, P95 220 to 455 ms | NextPlaid README |
| EmbeddingGemma | <15 ms per 256 tokens on EdgeTPU (no CPU figure) | Google blog |
| qmd hybrid `query` | warm ~10 s with HTTP daemon (0.9.0 era; hardware unstated) | qmd CHANGELOG |
| ColGREP agent (2B model) | ~75 to 90 s per question on CPU | colgrep README |

Index bytes per chunk (derived, label: inferred from dims, not measured):

- Single vector float32: dims x 4 bytes. 256-d static = 1 KiB; 384-d = 1.5 KiB; 768-d =
  3 KiB; 1024-d = 4 KiB per chunk, before ANN graph and metadata overhead. int8 storage
  divides by 4; binary by 32; MRL truncation scales linearly.
- ColBERT/PLAID: per token roughly a centroid id plus nbits x 128 / 8 bytes of residual
  (4 + 64 bytes at 4 bits, 4 + 32 at 2 bits). At ~300 tokens per unit that is roughly
  10 to 20 KiB per code unit; ColGREP's pooling (factor 2 halves) and 1-bit mode (~4x
  smaller) reduce it.
- Measured totals: Vera 4.7 GB vs Semble 32 GB across 63 repos (Vera doc); ck "~2x
  source" (vendor); qmd BM25-only ~26 MB for an 11.4 MB Markdown corpus (2026-05 brief).

Practical reading for a 4-vCPU CPU-only host: static embeddings (16 to 32 MB models)
make "index on first search" viable for repos up to tens of thousands of files; 100M+
transformer embedders need minutes to hours for first index and a background job or
daemon; LLM query expansion and LLM reranking add seconds per query.

## Suitability as an Optional Pluggable Semantic Backend

| Tool | Startup / daemon | Model download | Licence | Privacy | Verdict |
| --- | --- | --- | --- | --- | --- |
| Vera | none; ~0.13 s CLI (vendor) | ~32 MB (or none, keyword-only) | MIT | local; daily update check (disable) | **Pilot first** for code + docs |
| ck | none; MCP optional | ~67 MB bge-small | Apache-2.0 | local | **Pilot**; best location data (byte spans) |
| ColGREP | none | 17 MB INT8 model (2.5 GB only for agent mode) | Apache-2.0 | local | **Pilot**; best file-list scoping |
| Semble | Python ~0.7 s per call; use `--http` | ~33 MB | MIT | local | **Pilot** behind a persistent process |
| qmd | Node ~0.16 s per call; daemon for hybrid | none for BM25; ~2.25 GB for hybrid | MIT | local; trust gate for project configs | **Markdown/notes provider** (BM25 by default) |
| zvec-grep | daemon recommended | ~32 MB default | Apache-2.0 | local by default | Wait for JSON output |
| grepai, SeaGOAT, cocoindex-code | external daemons (Ollama, server, auto daemon) | Ollama / 1 GB torch | MIT / MIT / Apache-2.0 | local | Not first choice |
| mgrep, claude-context | cloud | n/a | Apache-2.0 / MIT | code leaves machine | Exclude by default |
| Serena | LSP servers | n/a | GPL-3.0-or-later | local | Exclude (licence, different job) |

## Changes Since May 2026

- **qmd** 2.1.0 (April) to 2.9.0: metadata frontmatter filtering, document processors,
  OpenAI-compatible remote embeddings, AST chunking option, MCP HTTP hardening (Origin /
  Host checks), per-index embed lock, project-config trust gate (2.8.3), faster
  multi-collection BM25.
- **`qntx-labs/qmd` renamed to `qntx/meme`**, now a Rust port of qmd 2.8.3 (1.0.0,
  2026-11-07, 48 stars).
- **Vera** moved to the VeraTools org and reached v2.x with potion-code default and a
  keyword-only mode.
- **New:** zvec-grep (July), Semble's growth to 6.5k stars and its public 1,251-query
  benchmark (used by Vera and ColGREP too), ColGREP agent mode and LateOn-Code models,
  blink-code-16M (2026-11-24), potion-code-16M-v2 (2026-07), EmbeddingGemma 2 (HF repo
  2026-09-14, Apache-2.0), jina-embeddings-v5-text (February, CC-BY-NC).
- **grepai** reached 1.x (October 2026). **ck** 0.8 (October). **Octocode** 0.30,
  **codanna** 0.18, **cocoindex-code** 0.2.44, **codesearch** 1.8.
- **Serena** application relicensed to GPL-3.0-or-later.
- **Slowed or stale:** osgrep, mgrep, ogrep (no release since 2026-05-03), sqlite-vec
  (still alpha, no release since 2026-05-18), semtools (no release since March),
  jina-grep. **Archived:** bloop. **Gone:** `sourcegraph/cody` repo (404).
- **Continue** marks `@codebase` indexing deprecated.

## Open Questions / UNVERIFIED

- zvec-grep: reranker, chunking details, index file format, MCP result schema, whether a
  JSON CLI output is planned; the `zvec` engine's licence.
- Whether ck's `--jsonl` semantic results are written incrementally or after ranking.
- ColGREP JSON schema (README shows `.[] | .unit.file`; not smoke-tested to avoid a model
  download).
- qmd embeddinggemma CPU throughput on 4 vCPU (no published number; benchmark agent).
- Semble 0.7.3 uses potion-code-16M-v2 while the README on `main` names
  blink-code-16M-int8; which release switches is UNVERIFIED.
- The CPU hardware behind Semble's speed table is not stated.
- ColGREP quality: 0.846 (vendor, H100 FP32) vs 0.693 (Semble run, CPU) on the same
  benchmark; INT8 CPU quality UNVERIFIED.
- Octocode default local model; LEANN default embedder; meme's model set and index.
- Meilisearch licence terms for the current release.
- EmbeddingGemma 2 release date and GGUF/ONNX availability from Google (community
  conversions exist on HF).
- Reason the `sourcegraph/cody` repository returns 404.
- Semble's benchmark queries and labels were generated by Claude Sonnet 4.6 and judged by
  the same model; independent replication of the 1,251-query results is not available.
