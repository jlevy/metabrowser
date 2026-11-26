# Keyword and Structural Search CLI Landscape (late November 2026)

Working notes for the 2026-11-26 refresh of the 2026-05 brief. Scope: literal, regex,
fuzzy, and syntax-aware search tools, plus the keyword (BM25) side of hybrid tools.
Semantic and embedding retrieval is covered in a separate note.

All facts were checked on **2026-11-26** unless a row says otherwise. Sources are primary
(GitHub API release and repository metadata, raw README/CHANGELOG files, crates.io, npm,
PyPI, Go module proxy) unless marked as a vendor claim. Stars are GitHub API counts on the
check date and are only an adoption hint. Anything not confirmed is marked **UNVERIFIED**.

Local checks were limited to `--version`/`--help` and a few tiny probes on a shared Linux
x86_64 VM (4 vCPU, 15 GB RAM). No benchmark numbers in this note were measured here except
the rough output-size probe in [Output efficiency](#output-efficiency-bytes-per-result).

## Executive Summary

- **ripgrep 16.0.0 shipped on 2026-11-22**, its first major release since 15.0 (2025-10).
  For an embedding application the important additions are `--in`/`--in0` (read the list
  of paths to search from a file or stdin, NUL-separated with `--in0`), `--max-bytes`
  (cap bytes read per file), `-G/--glob-not`, `RIPGREP_THREADS`, and a fix so `--json`
  reports every match in multiline mode. ripgrep remains the default exact-search tool and
  the strongest no-index backend: streaming JSON Lines with byte offsets and submatch
  spans, context lines as typed `context` events, clean exit on SIGPIPE and SIGINT, and
  the `grep-*`/`ignore` crates for in-process use. It still has **no global result cap**:
  `-m` caps matches per file, and the caller must stop reading and kill the process. That
  is exactly what VS Code does.
- **No new grep has displaced ripgrep for no-index scans.** ugrep (7.8.5, 2026-09-15) is
  still the feature-maximal alternative: fuzzy `-Z`, Boolean `-%`, archives,
  `--max-files`, and an optional index. Its `--json` is one JSON array, not JSON Lines,
  and context options are ignored by its `--format`-based output.
- **The 2026 trend is indexed grep for agents.** Cursor's sparse n-gram post (2026-03-23)
  set it off. `microsoft/tgrep` (created 2026-04-03, v1.2.9 on 2026-11-25, MIT) is the
  serious entrant: a trigram index with a watcher-backed server, **ripgrep-compatible
  `--json`**, and a global `--max-results` that ripgrep lacks. Smaller Rust clones (ngi,
  trigrep, xgrep, fastripgrep) are low-adoption. Zoekt is unchanged in model (positional
  trigrams, shards of about 3.5x the corpus) but gained `zoekt-local-sync` (2026-07-29).
  **Google `codesearch` is now archived**; its last commit was 2026-08-30.
- **Ranked keyword search without an index is now a category.** `boyter/cs` (v3.2.0)
  and `probe` (0.6.0-rc347) compute BM25 on the fly over a ripgrep-style scan. `qmd
  search` (2.9.0) is BM25 over a persistent SQLite FTS5 index (`porter unicode61`
  tokenizer) at document granularity.
- **Structural search consolidated on ast-grep** (0.51.3, 2026-11-16). It added an
  `outline` command (symbols, imports and exports as streaming JSON), deprecated the `sg`
  alias (which collides with shadow-utils `sg` on Linux), and added Zig and Markdown.
  Opengrep 2.0 (2026-11-13) dropped its Python wrapper to become a single ~160 MB binary.
  Comby has had no release since 2022; master was ported to OCaml 5 in 2026. gogrep
  (mvdan) is archived.
- **Embeddable libraries:** the Rust `grep-searcher`/`grep-regex`/`ignore` crates were
  re-released with ripgrep 16. `fff` (dmtrKovalenko, v0.11.0) is a resident file and
  content index with a watcher, frecency, and fuzzy/regex/plain grep. It ships Rust, C,
  Node/Bun, **Python (`fff-search` on PyPI)** and MCP front ends. Python ripgrep bindings
  remain weak: the most active, `ripgrep-rs` 0.4.5, is a three-star fork that returns
  whole lists. The PyPI name `ripgrep` is a third-party wheel whose provenance points to a
  personal fork, not upstream.
- **For Metabrowser's pluggable keyword provider:** the evidence favors (1) an optional
  ripgrep subprocess adapter using `--json` plus `--in0` for explicit file sets, with
  caller-side result caps, excerpt truncation and kill-on-cancel; (2) the planned bounded
  internal Python scanner as the zero-dependency fallback; and (3) for Phase 4 indexing,
  **SQLite FTS5 with the `trigram` tokenizer through the Python standard library**, kept
  fresh from Metabrowser's existing inventory events. FTS5 adds no new dependency and gives
  path filtering, BM25 and snippets in SQL. tantivy-py, tgrep and fff are credible
  alternatives to benchmark, and Zoekt is heavier than this use needs. See [Backend
  comparison](#backend-comparison-for-a-pluggable-keyword-provider).

## Master Comparison Table

Latest versions are as of 2026-11-26. "Index" means a persistent index. Licenses are SPDX
IDs from the GitHub API where available.

| Tool | Lang | Latest (date) | License | Model | Index | Machine output | Library / API | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ripgrep `rg` | Rust | 16.0.0 (2026-11-22) | Unlicense OR MIT | Rust `regex` (finite automata, SIMD literal prefilters); optional PCRE2 | no | `--json` JSONL, `--vimgrep`, `-0` | `grep`, `grep-searcher`, `grep-regex`, `ignore` crates | very active |
| ugrep | C++ | 7.8.5 (2026-09-15) | BSD-3-Clause | RE/flex DFA + SIMD; PCRE2 `-P`; fuzzy `-Z`; Boolean `-%` | optional (`ugrep-indexer`) | `--json` (array), `--csv`, `--xml`, `--format` | none (CLI) | active |
| GNU grep | C | 3.12 (2025-04-10) | GPL-3.0 | DFA/regex, PCRE2 `-P` | no | none (`-Z`, `-b`, `-c`, `-l`) | none | slow cadence |
| git grep | C | git 2.56.1 (2026-10-26) | GPL-2.0 | POSIX/PCRE2 over worktree, index, or trees | uses git index | none (`-z`, `--column`, `-c`, `-l`) | none | active |
| the_silver_searcher `ag` | C | 2.2.0 (2018) | Apache-2.0 | PCRE | no | `--vimgrep`, `--ackmate` | none | unmaintained (last push 2024-06) |
| ack | Perl | 3.10.0 (2026-06-07, CPAN) | Artistic-2.0 (NOASSERTION on GitHub) | Perl regex | no | `--output` templates | Perl | maintained, niche |
| sift | Go | v0.9.2 (2026-06-30) | GPL-3.0 | Go `regexp` | no | grep-like | none | minimal revival |
| fd | Rust | v10.5.2 (2026-11-07) | Apache-2.0 / MIT | filename regex/glob | no | `-0`, `--format`, `--max-results` | none | active |
| fzf | Go | v0.75.0 (2026-11-07) | MIT | fuzzy (Smith-Waterman-like v2) | no | `--filter` (non-interactive), `--listen` HTTP | Go package (used "as a library") | very active |
| skim `sk` | Rust | v5.9.0 (2026-10-27) | MIT | fuzzy | no | `--filter` | `skim` crate | very active |
| television `tv` | Rust | 0.15.9 (2026-06-14) | MIT | fuzzy (nucleo) | no | TUI-first | none | quieter since June |
| nucleo | Rust | nucleo 0.5.0 (2024-04), matcher 0.3.1 | MPL-2.0 | fuzzy matcher library | no | n/a | crate | low cadence (pushed 2026-06) |
| frizbee | Rust | v0.13.0 (2026-08-13) | MIT | SIMD Smith-Waterman fuzzy | no | n/a | crate | active |
| fff | Rust | v0.11.0 (2026-09-21) | MIT | plain (SIMD memmem), regex, fuzzy grep + frecency path search | in-memory + watcher | MCP, typed SDK results | Rust, C, Node/Bun, Python (`fff-search`) | very active |
| ast-grep | Rust | 0.51.3 (2026-11-16) | MIT | tree-sitter AST patterns, YAML rules, ESQuery selectors | no | `--json=stream\|compact\|pretty` | `ast-grep-core` crate, `@ast-grep/napi`, `ast-grep-py`; LSP; official MCP repo | very active |
| semgrep | OCaml/Python | 1.187.0 (2026-11-24) | LGPL-2.1 | semantic patterns, taint | no | `--json`, `--sarif` (end of run) | none stable | very active |
| opengrep | OCaml | v2.1.0 (2026-11-25) | LGPL-2.1 | semgrep fork, interfile taint | no | semgrep-compatible JSON/SARIF | none | very active |
| comby | OCaml | 1.8.1 (2022-06-28) | Apache-2.0 | language-aware holes `:[x]` | no | `-json-lines`, `-match-only` | none | no release since 2022; master active (OCaml 5) |
| srgn | Rust | 0.14.4 (2026-11-15) | MIT | regex scoped by tree-sitter queries | no | text only (no JSON found) | `srgn` crate | active again |
| gogrep (mvdan) | Go | none | BSD-3-Clause | Go AST patterns | no | text | n/a | **archived** |
| tree-sitter CLI `query` | Rust | v0.27.2 (2026-11-07) | MIT | S-expression queries | no | text only | `tree-sitter` crates/bindings | very active |
| ripgrep-all `rga` | Rust | v0.10.10 (2025-11-09) | AGPL-3.0 (NOASSERTION on GitHub; UNVERIFIED) | rg + adapters (PDF, Office, archives, SQLite) | adapter cache | rg `--json` passthrough (UNVERIFIED) | none | maintenance mode |
| Zoekt (Sourcegraph) | Go | pseudo-version 2026-11-25 (no tags) | Apache-2.0 | positional trigram index, regex, BM25 option, symbol ranking | yes (~3.5x corpus) | CLI `-jsonl`; HTTP JSON; gRPC streaming | Go packages | active |
| Google codesearch | Go | v1.2.0 (2020); master 2026-08-30 | BSD-3-Clause | trigram index + RE2 | yes | grep-like text | Go `index`, `regexp` packages | **archived** |
| livegrep | C++/Go | no releases; last commit 2026-02-10 | BSD-2 (NOASSERTION on GitHub; UNVERIFIED) | suffix-array index | yes (in memory) | gRPC backend + web | gRPC | slow |
| Hound | Go/JS | v0.7.1 (2023-05-03); commits 2026-11 | MIT | trigram (codesearch lineage) | yes | HTTP JSON API | HTTP | maintenance |
| microsoft/tgrep | Rust | v1.2.9 (2026-11-25) | MIT | trigram index, Rust `regex`/fancy-regex verify | yes (`.tgrep/`) + watcher server | rg-compatible `--json`, `--max-results` | JSON-RPC over loopback TCP; `tgrep-core` | new, very active |
| Sourcegraph `src` | Go | 8.2.0 (2026-11-11) | Apache-2.0 | remote Sourcegraph (Zoekt-backed) | remote | `-json`, `-stream` | GraphQL/stream API | active |
| `gh search code` | Go | gh v2.106.0 (2026-11-25) | MIT | GitHub **legacy** code-search API | remote | `--json path,repository,sha,textMatches,url` | REST | active |
| probe | Rust (+npm) | v0.6.0-rc347 (2026-11-11) | Apache-2.0 (npm says ISC) | rg-style scan + tree-sitter blocks + BM25/TF-IDF | no | `--format json\|xml\|markdown` | npm SDK, MCP | very active, perpetual RC |
| cs (boyter) | Go | v3.2.0 (2026-09-11) | MIT | no-index scan + BM25 + structural boosts | no | `-f/--format text\|json\|vimgrep`, HTTP mode, MCP | HTTP | active |
| qmd `search` (BM25 side) | TypeScript | @tobilu/qmd 2.9.0 (2026-11-17) | MIT | SQLite FTS5 BM25, `porter unicode61` | yes (SQLite) | `--format json\|files\|csv\|md\|xml` | Node SDK, MCP, HTTP `/search` | very active |
| tantivy / tantivy-cli | Rust | tantivy 0.27.0 crate (2026-10-17); CLI 0.25.0 (2025-08-20) | MIT | Lucene-style inverted index, BM25 | yes | CLI JSON docs; `serve` HTTP | crate; `tantivy` PyPI 0.27.0 | engine active, CLI lagging |
| SQLite FTS5 | C | SQLite 3.54.1 (2026-10-16) | public domain | inverted index; `unicode61`/`porter`/`trigram` tokenizers; BM25 | yes | SQL rows; `snippet()`, `highlight()` | every SQLite binding incl. Python stdlib | very active |
| Meilisearch | Rust | v1.58.0 (2026-11-23) | MIT core + enterprise (NOASSERTION) | typo-tolerant server | yes | HTTP JSON | HTTP | server, not a CLI backend |
| Typesense | C++ | v30.2 (2026-04-19) | GPL-3.0 | typo-tolerant server | yes | HTTP JSON | HTTP | server, not a CLI backend |

Library-level engines:

| Engine | Ecosystem | Version (date) | Notes |
| --- | --- | --- | --- |
| `regex` / `regex-automata` | Rust | 1.13.2 / 0.4.19 (2026-11-19) | Linear-time guarantees; the engine behind rg, tgrep, fff regex mode |
| `memchr`, `aho-corasick` | Rust | 2.8.3 (2026-07-08), 1.1.5 (2026-08-03) | SIMD substring and multi-literal search |
| `grep` facade, `grep-searcher`, `grep-regex`, `grep-printer` (JSON printer), `grep-pcre2`, `ignore`, `globset` | Rust | 0.4.2 / 0.1.18 / 0.1.15 / 0.3.2 / 0.1.11 / 0.4.35 / 0.4.22 (all 2026-11-22) | ripgrep's own components; `grep-printer` contains the `--json` printer |
| Hyperscan | C | 5.4.2 (2023); Intel releases from 5.5 are proprietary | Multi-regex DFA; use Vectorscan instead |
| Vectorscan | C | 5.4.14 (2026-11-09) | BSD fork of Hyperscan; ARM/Power/SIMDe; Python `hyperscan` 0.9.1 (2026-10-08) binds Hyperscan/Vectorscan (UNVERIFIED which) |
| Go `regexp`, `index/suffixarray` | Go | Go 1.27.4 current | RE2 semantics; `suffixarray` gives substring lookup over an in-memory byte slice |
| `google-re2`, `pyre2` | Python | 1.1.20251105, 0.3.14 (2026-09-25) | RE2 bindings |
| `@vscode/ripgrep` | npm | 1.18.0 (2026-05-07) | Ships platform packages; **linux-x64 binary is rg 15.0.0** (checked by running it) |
| `ripgrep` (npm, pithings) | npm | 0.3.1 (2026-04-06) | ripgrep compiled to WASM, embedded z85+brotli, no native binary |

## Streaming and Scoping Capability Matrix

This matrix answers the Metabrowser requirements: (a) stream results, (b) filter a
rendered view (tree, treemap) to matching files, (c) scope to subtrees or an explicit
file set, and (d) pull snippets with context. Cells cite flag names. "Caller kill" means
the tool has no global cap, so the embedding process must stop reading and terminate it.

### No-index scanners and structural tools

| Tool | Incremental machine stream | Files-with-matches (b) | Per-file counts | Subtree / glob scoping (c) | Explicit file list (c) | Context in machine output (d) | Result bounding / early stop | Ignore / hidden / binary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rg 16 | Yes: `--json` JSONL, `begin`/`match`/`context`/`end`/`summary`; per-file blocks emitted whole; order nondeterministic unless `--sort=path` (single-threaded) | `-l` (not combinable with `--json`) | `-c`, `--count-matches` (not with `--json`); JSON `end.stats` per file | path args, `-g/--glob`, `-G/--glob-not` (new), `-t/-T`, `--max-depth` | **`--in FILE`, `--in0 FILE`** (new in 16; `-` = stdin); explicit paths bypass ignore rules (tested) | Yes: `-A/-B/-C` produce `context` events with `line_number` and `absolute_offset` | `-m` per file, `--max-filesize`, **`--max-bytes`** (new), `--max-columns` (**ignored by `--json`**); no global cap, so caller kill; exits 0 on SIGPIPE, 130 on SIGINT (tested) | gitignore/.ignore/.rgignore; hidden and binary skipped by default; `-u`…`-uuu`; `--no-require-git`; `-z` decompression |
| ugrep 7.8.5 | Partial: `--json` is one JSON array built from `--format-*` templates, bytes stream but not JSONL; `--format` can emit custom JSONL | `-l` | `-c` | path args, `--include/--exclude`, `-t`, `--depth=MIN,MAX` | argv only (no `--files-from` found; `--include-from` is globs) | **No**: README says `--format` ignores `-A/-B/-C/-y`; `--json` is a `--format` preset | `-m MIN,MAX`, **`--max-files=NUM`** (global file cap), `-K` line range | `--ignore-files`; `-I` binary; `-.` hidden; `-z` archives |
| GNU grep 3.12 | Text only | `-l`, `-L` | `-c` | `-r`, `--include`, `--exclude-dir` | argv / `xargs -0` | text `-A/-B/-C` | `-m` per file | no gitignore; `-I` binary; `-Z` NUL after names; `-b` byte offset |
| git grep | Text only | `-l`, `-L` | `-c` | pathspecs after `--`, `--max-depth` | pathspecs (argv) | text `-A/-B/-C`, `-W` function context | `-m/--max-count` per file | tracked files by default; `--untracked`, `--no-index`; `-z`; `--column` |
| tgrep 1.2.9 | Yes: rg-compatible `--json` stream | `-l` | `-c`, `--count-matches` | path args, `-t`, globs (flags mirror rg) | UNVERIFIED (no `--in` found in README) | Yes (rg-shaped `context` events) | `-m`, **`--max-results N`** (global, stops after the file reaching N; server stops reading candidates) | rg semantics; `--no-require-git` |
| ast-grep 0.51.3 | Yes: `--json=stream` JSONL, one object per match | `--files-with-matches` (not with `--json`) | no | path args, `--globs`, `-l/--lang` | argv; `--stdin` for one buffer | `-A/-B/-C` (JSON carries `lines` of the match; context in JSON UNVERIFIED) | none; caller kill | ignore-aware; `--no-ignore hidden\|dot\|vcs…` |
| semgrep / opengrep | No: one JSON/SARIF document at end; `--incremental-output` requires `--experimental` (semgrep) | via JSON post-processing | no | `--include/--exclude` | argv targets | JSON includes `lines` (no context flag) | `--max-target-bytes`, `--timeout`, `--max-memory` | `.semgrepignore`, gitignore |
| comby 1.8.1 | `-json-lines` (one line per file with matches) | `-match-only` + JSON | `-count` | `-d`, `-f` extensions, `-exclude`, `-exclude-dir` | argv/`-stdin` | no | `-bound-count`, `-timeout`; `-ripgrep` pre-filters files with rg | via `-ripgrep` |
| srgn 0.14.4 | Text search mode only (no JSON flag found in source) | UNVERIFIED | no | `--glob` (UNVERIFIED) | stdin buffer or glob | no | n/a | n/a |
| tree-sitter `query` 0.27.2 | Text only; needs compiled grammars | no | no | file args | **`--paths FILE`** | no | `--byte-range`, `--row-range` | none |
| rga 0.10.10 | rg output passthrough (UNVERIFIED for `--json`) | `-l` | `-c` | rg flags | rg flags | rg flags | rg flags | rg + adapter cache |
| probe rc347 | No: ranked results emitted after scoring (inferred from BM25 ranking) | via JSON | no | path args, query `ext:`/`lang:` filters | argv | AST block, not lines | **`--max-results`, `--max-tokens`, `--max-bytes`** | gitignore |
| cs 3.2.0 | UNVERIFIED (ranked, so likely end-of-scan) | UNVERIFIED | no | `--dir`, filters | UNVERIFIED | ranked best snippet | UNVERIFIED | gitignore |
| fd 10.5.2 | filenames only, `-0` | n/a | n/a | path args, `-e`, `-g`, `--exact` (new) | n/a | n/a | `--max-results`, `-1` | gitignore; `--ignore-parent` (new) |
| fzf `--filter` | sorted list after reading all input | n/a | n/a | input is the scope | stdin | n/a | `--filter` + `head`; exits 1 on no match | n/a |
| fff (SDK/MCP) | Paged: `grep` returns up to 100 lines/page (max 200) with a resumable cursor | `find_files`; SDK results carry paths | `total_matched` | MCP `paths`, `globs`, `hidden`; SDK `cwd` | MCP `paths` list | `before_context`/`after_context` (Python) | `maxResults` + cursor; fuzzy stages have 2 s budgets | ignore walker (ripgrep `ignore` crate); git status per result |
| ripgrep-rs (Python) | No: `search()` returns formatted text or JSONL string (inferred from README) | `files()` lists files | no | globs, path args | path list | `before_context`/`after_context` | `max_count` per file | gitignore |

### Indexed engines

| Engine | Index structure | Ranking | Filter by path prefix / file set | Freshness | Output / API | Index cost |
| --- | --- | --- | --- | --- | --- | --- |
| Zoekt | positional trigrams in mmap'd shards | symbol and code signals; `UseBM25Scoring` option in JSON API | query atoms `file:` (regex, so `file:^src/` for a prefix), `repo:`, `lang:`, `-file:`; `RepoIDs` filter | rebuild a repo's shard with `zoekt-index` / `zoekt-git-index`; `zoekt-local-sync` (new 2026-07) syncs a tree of repos; `zoekt-indexserver` polls code hosts | CLI `-jsonl`, `-l`; webserver `-rpc` JSON `/api/search` with `NumContextLines`; gRPC streaming | shard ~**3.5x corpus**; ~1.2x corpus RAM when postings are on SSD (design doc) |
| Google codesearch | trigram posting lists (single file) | none | `csearch -f FILEREGEXP` | `cindex` with no args re-indexes all added paths (full rescan) | grep-style text, `-l`, `-c`, `-n`; Go packages | small; UNVERIFIED ratio |
| tgrep | trigram index in `.tgrep/` | none (grep order; `--sort`) | path args and globs, rg-style | `tgrep serve` watches (native or poll) and refreshes asynchronously; without a server, rerun `tgrep index`; `--no-index` forces a scan; `status` shows lag | rg-compatible JSON; JSON-RPC 2.0 over loopback TCP | build "22.6 s, 160 MiB peak" in a README example; disk preflight assumes up to 3x candidate bytes during build |
| ugrep `--index` | per-directory index files from `ugrep-indexer` (format UNVERIFIED) | none | same as ugrep scan | **safe by design**: files changed after indexing are always searched (mtime vs index time); re-index is incremental | same as ugrep | example: 5.6 MB for 12 MB of files (~4.3 KB/file) |
| qmd `search` | SQLite FTS5 (`porter unicode61`), plus a CJK path | BM25 (`Math.abs(score)`, typically 0 to 25+) | `-c/--collection` (OR), `--filter` metadata AST; **no path-prefix or explicit file-set flag** in the CLI options list | explicit `qmd update` (reports new/updated/unchanged/removed); optional per-collection pre-update hook; no watcher | `--format json\|files\|csv\|md\|xml` (JSON is a whole array; `-n` defaults to 5, or 20 for json/files); HTTP `/search`; MCP | 26 MB for the 2026-05 brief's 310-file, 11.4 MB corpus (from that brief) |
| tantivy | Lucene-style segments | BM25 | index `path` as a raw (untokenized) field, then filter with term-set or range/regex queries (inferred from the API, not tested) | application commits added/deleted docs; segment merges | crate API; tantivy-cli `search` prints JSON docs, `serve` gives HTTP | depends on schema (positions, stored fields); UNVERIFIED ratio |
| SQLite FTS5 | inverted index; `trigram` tokenizer enables substring matching for queries of three or more characters | `bm25()` | ordinary SQL: `WHERE path >= 'src/' AND path < 'src0'`, `IN (...)`, or a join with a temp table of selected files | application `INSERT/UPDATE/DELETE` (triggers or event-driven); fully transactional | `snippet()`, `highlight()`, `LIMIT`; rows stream as the cursor steps; `Connection.interrupt()` cancels | trigram indexes are large (UNVERIFIED ratio, measure) |
| fff (in-memory) | in-memory file list + content cache | frecency + fuzzy scores | `paths`, `globs` | background watcher; `reindex()` | typed SDK objects; MCP | RAM only; UNVERIFIED size |
| Hound | trigram per repo (codesearch lineage) | none | `files` regex parameter (UNVERIFIED) | polls repos on an interval | HTTP JSON | UNVERIFIED |
| livegrep | suffix arrays in memory | none | file/repo regex atoms (UNVERIFIED) | rebuild index file | gRPC + web | in-memory, large |
| Sourcegraph `src` | remote (Zoekt + searcher) | Sourcegraph ranking | query `file:`/`repo:` | server-managed | `-json`; `-stream` with `-display N` | n/a |
| `gh search code` | GitHub legacy code-search index | GitHub's | `--filename`, `--extension`, `--repo`, `--owner`, `--language`, `--match file\|path` | GitHub-managed | `--json` fields `path, repository, sha, textMatches, url`; `-L` default 30; no regex via API | n/a |

## Output Efficiency (bytes per result)

A rough probe, not a benchmark: `rg 16.0.0 -i search docs` over this repository's `docs/`
tree. That is prose Markdown with long lines, so absolute sizes are high. There were 717
matching lines in 110 files.

| Mode | Total bytes | Per matching line | Ratio to plain |
| --- | ---: | ---: | ---: |
| `-n --no-heading` | 139,484 | ~195 B | 1.0x |
| `--vimgrep` (one row per match) | 204,464 | ~285 B | 1.5x |
| `--json` | 312,649 | ~436 B | 2.2x |
| `--json -C1` | 641,916 | ~895 B | 4.6x |
| `-l` (per file) | 6,686 | ~61 B/file | n/a |
| `-c` (per file) | 6,928 | ~63 B/file | n/a |

On a short code line, a JSON `match` event is about 150 to 200 bytes of envelope plus
twice the line length plus about 50 bytes per submatch. ast-grep `--json=stream` is about
430 bytes for a 15-character match (it includes metavariable ranges). ugrep `--json`
should be close to plain size plus a short key set, but it was not measured. **The
benchmark agent should measure bytes and tokens per result for each tool on code and on
Markdown.** It should also measure the cost of `--json -C2`, since context lines dominate
size.

Implication for Metabrowser: transfer bounded excerpts, not raw rg JSON. The adapter
should truncate `lines.text` around the submatch spans (`-M` does not apply under
`--json`) and should base64-decode `bytes` lines or drop them.

## Per-Tool Notes

### ripgrep (`rg`)

- 16.0.0 released 2026-11-22; 15.2.0 on 2026-07-15 (traversal speedups, aarch64 musl
  binaries, gitignore fixes). Source:
  [CHANGELOG](https://github.com/BurntSushi/ripgrep/blob/master/CHANGELOG.md),
  [release 16.0.0](https://github.com/BurntSushi/ripgrep/releases/tag/16.0.0).
- 16.0 highlights: `--in`/`--in0` (paths from a file or stdin, as if given positionally),
  `-G/--glob-not`, `--max-bytes`, `RIPGREP_THREADS`, POSIX bracket classes, compressed
  files detected by magic number, control codes sanitized in printed paths, and `--json`
  emitting all matches in multiline mode (#1983). The linked
  [grep crates](https://crates.io/crates/grep-searcher) were bumped the same day.
- The search model is the Rust `regex` engine (finite automata, no backtracking) with
  SIMD literal prefilters; `-P`/`--engine=pcre2` gives PCRE2 10.45 with JIT in release
  binaries (confirmed by `rg --version`). Parallel directory walk via `ignore`.
- JSON format: `begin`, `match`, `context`, `end` (with per-file stats), and `summary`.
  Each match carries `path`, `lines`, `line_number`, `absolute_offset` (byte offset of
  the line), and `submatches[]` with byte `start`/`end` in the line. Non-UTF-8 data
  appears as `{"bytes": base64}`. The schema has been stable since rg 0.10 and is
  documented in `grep-printer`. `--json` cannot be combined with `-l`, `-c`, `--files`,
  or `--count-matches`, and it implies `--stats`.
- Interfaces: CLI; Rust crates; `@vscode/ripgrep` npm (rg 15.0.0); WASM npm `ripgrep`;
  PyPI `ripgrep-bin` 16.0.0 (third-party [pip-binary-factory](https://github.com/Bing-su/pip-binary-factory)
  repack). Community MCP `mcp-ripgrep` 0.4.0 (2025-04, stale).
- **VS Code's text search is ripgrep.**
  [`ripgrepTextSearchEngine.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/services/search/node/ripgrepTextSearchEngine.ts)
  spawns `rg --hidden --no-require-git ... --no-config --json`. It applies `maxResults`
  and preview truncation in its own parser and calls `rgProc.kill()` on cancellation or
  when the limit is hit. This is the reference embedding pattern.
- Install: static musl tarball 2.2 MB (16.0.0 x86_64), `.sha256` alongside; Homebrew,
  apt, cargo. Supply-chain note: the PyPI package **`ripgrep` 15.1.0** names Andrew
  Gallant as author, but its PyPI attestation's publisher is a personal fork repository
  (`FlavioAmurrioCS/ripgrep`), not upstream. Treat it as third-party.
- Performance: README table (i9-12900K, Linux kernel tree): `rg -n -w '[A-Z]+_SUSPEND'`
  took 0.082 s, against ugrep 0.639 s, ag 0.443 s, and git grep 0.273 s with `-P`
  (author's benchmark). Cost is O(bytes scanned) per query; latency is dominated by
  directory walk and page cache at repo scale and by I/O at monorepo scale.
  [README](https://github.com/BurntSushi/ripgrep#quick-examples-comparing-tools).

### ugrep

- 7.8.5 (2026-09-15): `--encoding` fixes, xz/lzma decoding limits, mode-flag ordering.
  7.8.3 and 7.8.4 capped DFA memory (worst case stated as 1 to 2 GB) and fail fast on
  complex patterns. [Releases](https://github.com/Genivia/ugrep/releases).
- Features: fuzzy `-Z[best][+-~]MAX`; Boolean `-%`/`--bool`, with `-%%` applying it
  file-wide; archives and compressed files `-z --zmax`; `--filter` for PDF and Office via
  external tools; `--encoding`; TUI `-Q`; `--sort=best|size|changed`; `--max-files`.
  [README](https://github.com/Genivia/ugrep/blob/master/README.md).
- Machine output: `--json` is a JSON array whose structure is defined by `--format`
  presets (`"file"`, `"matches": [{"line","column","offset","match"}]`), and `--format`
  ignores context options. A custom `--format` can emit JSON Lines but loses context.
- Index: `ugrep-indexer` v1.0.0 (2024-04-18). The vendor reports a 21x speedup on a
  **cold** filesystem and says indexed search never skips updated files.
  [ugrep-indexer](https://github.com/Genivia/ugrep-indexer).
- Install: **no Linux release binaries**; only a Windows zip is attached. Build from
  source (`./build.sh`, optional PCRE2, zlib, and other libraries), or use Homebrew or
  distro packages. Vendor benchmarks are at
  [ugrep-benchmarks](https://github.com/Genivia/ugrep-benchmarks) (pushed 2025-06). They
  conflict with ripgrep's README table; treat both as vendor claims.

### GNU grep, git grep, ag, ack, sift

- GNU grep 3.12 (2025-04-10) is still current ([ftp.gnu.org](https://ftp.gnu.org/gnu/grep/)).
  It has no JSON or gitignore support. Useful flags are `-Z`, `-b`, `-m`, `-c`, and `-l`.
- git 2.56.1 (2026-10-26). `git grep` supports `-m/--max-count`, `--column`, `-z`,
  `--untracked`, `--no-index`, `--threads`, `-o`, and `--and/--or/--not`. It has no JSON.
  Only it can search the index or old trees. [Docs](https://git-scm.com/docs/git-grep).
- ag: no release since 2.2.0 (2018); last push 2024-06. Do not adopt.
- ack 3.10.0 (2026-06-07, [MetaCPAN](https://metacpan.org/dist/ack)). Perl; slowest in
  rg's table.
- sift v0.9.2 (2026-06-30) only adds a no-follow-symlinks option, after v0.9.1
  (2025-09) and v0.9.0 (2016). [Releases](https://github.com/svent/sift/releases).
- uutils/grep 0.2.0 (2026-08-27): a new Rust GNU-grep reimplementation (148 stars). Watch
  only.

### Fuzzy finders and matchers (fd, fzf, skim, television, nucleo, frizbee, fff)

- fd v10.5.2 (2026-11-07). 10.5.0 added `--exact` and `--ignore-parent`, and 10.5.x
  sanitizes control and bidi characters for terminals and writes raw bytes in `--format`
  pipes. [CHANGELOG](https://github.com/sharkdp/fd/blob/master/CHANGELOG.md).
- fzf v0.75.0 (2026-11-07). 0.74.2 and 0.74.3 made short and non-ASCII queries up to 2.4x
  to 16x faster (vendor). 0.75.0 fixed an O(n^2) `--listen` request parser (a 1 MB
  request could block about 30 s), and 0.74.5 fixed fzf-tmux and zsh FIFO security
  issues. `--filter` is the non-interactive mode and exits non-zero on no match.
  [CHANGELOG](https://github.com/junegunn/fzf/blob/master/CHANGELOG.md).
- skim v5.0.0 (2026-07-02) through v5.9.0 (2026-10-27): about 30 releases since May,
  Windows support, `--popup`. [Releases](https://github.com/skim-rs/skim/releases).
- television 0.15.9 (2026-06-14): a TUI channel launcher on nucleo; not a backend.
- nucleo (Helix): crate releases still 0.5.0 / matcher 0.3.1 (2024); repo pushed
  2026-06. frizbee v0.13.0 (2026-08-13) is SIMD Smith-Waterman, used by fff and blink.cmp.
- **fff** ([repo](https://github.com/dmtrKovalenko/fff), 11.3k stars, MIT, v0.11.0
  2026-09-21) is a library, not a CLI. One Rust core is exposed as the `fff-search` crate,
  `libfff_c`, `@ff-labs/fff-node`, **`fff-search` on PyPI** (abi3 wheels for Python
  3.10+, about 4.4 MB on manylinux_2_38 x86_64), an MCP server (`grep`, `find_files`,
  `multi_grep`), and a Neovim plugin. Content grep has plain (SIMD memmem), regex (Rust
  `regex`), fuzzy (Smith-Waterman) and multi-pattern Aho-Corasick modes, with context
  lines, cursor pagination, a background watcher and git status per result. Its claim to
  be faster than rg and fzf in long-lived processes is a vendor claim.

### Structural tools

- **ast-grep** 0.51.3 (2026-11-16). Since May it has added the `outline` command
  (0.44.0; streaming JSON of symbols, imports and exports; Markdown headings from 0.45.3),
  ESQuery-style selectors in `run` (0.43.0), Markdown (0.43.0) and Zig (0.50.0) support,
  a custom-language trust policy (0.50.0), and musl Linux binaries (0.51.2), and it
  deprecated the `sg` command (0.45.0). JSON styles are `stream`, `compact`, `pretty` (the
  default). Stream objects carry `text`, `range.byteOffset`, line/column for start and
  end, `file`, `lines`, `language`, and `metaVariables`. No global result cap. Bindings:
  `@ast-grep/napi`, `ast-grep-py`; `ast-grep lsp`; official
  [ast-grep-mcp](https://github.com/ast-grep/ast-grep-mcp) (500 stars, pushed
  2026-11-22). Release zip 9.2 MB; the `ast-grep` binary unpacks to 57 MB (bundled
  grammars). On Linux, `sg` collides with shadow-utils `sg`, as on this host.
  [CHANGELOG](https://github.com/ast-grep/ast-grep/blob/main/CHANGELOG.md).
- **semgrep** 1.187.0 (2026-11-24, PyPI). JSON and SARIF are emitted at the end of a run;
  `--incremental-output` requires `--experimental`; `--metrics` defaults to `auto`.
  [CLI reference](https://docs.semgrep.dev/cli-reference). A rules and security engine,
  not a navigation backend.
- **opengrep** v2.1.0 (2026-11-25). v2.0.0 (2026-11-13) removed Python and is a single
  binary (`opengrep_linux_x86`, 162 MB, with cosign `.sig`/`.cert`), with interfile taint
  under `--enable-interfile`.
  [Release](https://github.com/opengrep/opengrep/releases/tag/v2.0.0).
- **comby** 1.8.1 (2022) is still the latest release. Master moved to OCaml 5
  (2026-06-08) and replaced PCRE with `re` (2026-11-06), both unreleased. Flags
  `-json-lines`, `-match-only`, `-count`, `-ripgrep`, `-bound-count`, `-timeout`
  ([source](https://github.com/comby-tools/comby/blob/master/src/main.ml)). The x86_64
  Linux binary is 38.6 MB.
- **srgn** 0.14.3 and 0.14.4 (2026-11) came after a 9-month gap. It is grep-like with
  tree-sitter scopes (`--python 'class'`) and is more a rewrite tool than a search
  backend. [README](https://github.com/alexpovel/srgn).
- **gogrep**: `mvdan/gogrep` archived; `quasilyte/gogrep` v0.5.0 (2023) is idle.
- **tree-sitter CLI** v0.27.2. `tree-sitter query QUERY_FILE [PATHS] --paths FILE`
  accepts a file list but prints text only and needs grammars compiled locally. It suits
  building tools, not serving as a backend.

### Indexed code search

- **Zoekt** ([README](https://github.com/sourcegraph/zoekt), [design](https://github.com/sourcegraph/zoekt/blob/main/doc/design.md),
  [JSON API](https://github.com/sourcegraph/zoekt/blob/main/doc/json-api.md)) has no
  tags; install with `go install` at a pseudo-version (latest
  `v0.0.0-20261125095755-c639b2fafda5`). It needs Go 1.26 (go.mod sets `toolchain
  go1.27.3`). New since May: `zoekt-local-sync` (2026-07-29) and a single
  `ghcr.io/sourcegraph/zoekt` image. CLI flags: `-jsonl`, `-l`, `-r`, `-sym`. Universal
  ctags is recommended for symbol ranking.
- **Google codesearch** is archived. Its last commit (2026-08-30) was an index
  optimization; the Go proxy `@latest` is still v1.2.0 (2020), so use `@master` for
  2024+ fixes. `csearch [-c] [-f fileregexp] [-h] [-i] [-l] [-n] regexp`; no JSON.
- **microsoft/tgrep** ([README](https://github.com/microsoft/tgrep)), created 2026-04-03,
  3.5k stars, v1.2.9. The README says it is integrated into GitHub Copilot CLI (vendor
  claim, not verified). Its August 2026 benchmark sweep reports it faster than ripgrep in
  17 of 18 repo/platform combinations, from 0.93x to 51.9x, with a warm server and the
  index already built (vendor claim; indexing time excluded). Release binaries are
  musl-static, about 6.7 MB for x86_64 Linux; also Homebrew (`brew install tgrep`) and
  `cargo install --path tgrep-cli`. It needs Rust 1.88 to build.
- **livegrep**: no releases; bazel build; last commit 2026-02-10. **Hound**: v0.7.1
  (2023); recent commits are dependency bumps and an OpenBSD fix. Neither fits an
  embedded backend.
- **Sourcegraph `src`** 8.2.0. `src search -json`; `-stream` with `-display N`; needs an
  instance and token. [Docs](https://sourcegraph.com/docs/cli/references/search).
- **`gh search code`** (gh 2.106.0): still "powered by what is now a legacy GitHub code
  search engine", and regex is unavailable through the API.
  [Manual](https://cli.github.com/manual/gh_search_code).

### Ranked keyword search (BM25) without and with an index

- **probe** ([README](https://github.com/probelabs/probe)). Every release is
  `v0.6.0-rcNNN`, about 30 since May. The crates.io `probe-code` (0.6.0, 2025-07) is
  stale; use npm `@probelabs/probe` or the release tarball (10.5 MB musl). It uses
  Elasticsearch-style boolean queries, BM25/TF-IDF/hybrid rerankers, tree-sitter block
  extraction, `--max-tokens`, `--max-results` and `--format json`, and offers an MCP
  mode. The license is Apache-2.0 on GitHub but ISC in npm metadata, an inconsistency to
  flag in a supply-chain review.
- **cs** ([boyter/cs](https://github.com/boyter/cs)) v3.2.0: no-index BM25 with
  code/comment/string weighting and complexity "gravity"; TUI, HTTP (`cs -d`) and MCP
  (`--mcp`, `--git-sync`) modes.
- **qmd** `search` ([README](https://github.com/tobi/qmd)). npm package `@tobilu/qmd`
  2.9.0 (the unscoped npm `qmd` is an unrelated 2016 package). It needs Node 22+ and
  native `better-sqlite3`, and pulls `node-llama-cpp` even for BM25-only use. Its FTS5
  table uses `tokenize='porter unicode61'`
  ([store.ts](https://github.com/tobi/qmd/blob/main/src/store.ts)). 2.9.0 made
  collection-scoped BM25 exact and about 12x faster over 13 collections (vendor), added
  metadata filtering and an HTTP `/search` endpoint, and caps result bodies at 262,144
  characters. Results are **documents with a snippet**, not line matches. The concurrency
  rule from the 2026-05 brief (run sequentially) was partly addressed by a shared SQLite
  sidecar lock; benchmark again before relying on it.
- **tantivy**: crate 0.27.0 (2026-10-17) with no matching GitHub release (the latest
  GitHub release is 0.26.1, 2026-05-10). Python `tantivy` 0.27.0 (2026-10-22, official
  tantivy-py). tantivy-cli is stuck at 0.25.0 (2025-08-20) and is a demo tool (`new`,
  `index` from NDJSON, `search`, `serve`, `bench`). Use the library, not the CLI.
  [CHANGELOG](https://github.com/quickwit-oss/tantivy/blob/main/CHANGELOG.md).
- **SQLite FTS5**: SQLite 3.54.1 (2026-10-16), per the
  [chronology](https://www.sqlite.org/chronology.html). A probe here with Python 3.13's
  bundled SQLite 3.53.1 confirmed that `CREATE VIRTUAL TABLE ... USING
  fts5(body, tokenize='trigram')`, `snippet()`, `highlight()` and `bm25()` work, and that
  the substring query `eedl` matched `needle`. The trigram tokenizer gives
  grep-like substring search (case-insensitive by default; queries under three
  characters need a fallback) with SQL-native scoping.
  [FTS5 docs](https://www.sqlite.org/fts5.html).

### New entrants since May 2026 (keyword side)

Found by GitHub repository search for 2026-created repositories (grep, code search,
ripgrep, trigram, structural search, full-text search) sorted by stars, plus web search.
Star counts for very young agent-tool repositories can be inflated; treat them as weak
signals.

| Project | Created | Latest | Keyword relevance |
| --- | --- | --- | --- |
| [microsoft/tgrep](https://github.com/microsoft/tgrep) | 2026-04-03 | v1.2.9 (2026-11-25) | Indexed grep with rg-compatible JSON, `--max-results`, watcher server; **top candidate to benchmark** |
| [boyter/cs](https://github.com/boyter/cs) 3.x | older repo | v3.2.0 (2026-09-11) | No-index BM25 ranked code search |
| [thiagodmont/greeg](https://github.com/thiagodmont/greeg) | 2026-09-02 | v0.14.1 (2026-11-13) | rg-flag-compatible, index-backed, token-budgeted, definitions first; 330 stars |
| [xerj-org/xerj](https://github.com/xerj-org/xerj) | 2026-06-30 | v1.0.0-rc.105 (2026-11-23) | Rust BM25/vector/hybrid server with an Elasticsearch-compatible API; release binaries include proprietary crates that are not in the public source (per its README) |
| [zvec-ai/zvec-grep](https://github.com/zvec-ai/zvec-grep) (`zg`) | 2026-07-10 | v0.3.1 (2026-11-18) | "ripgrep, BM25, and vector search behind one interface"; mostly semantic |
| [redhat-et/ripwire](https://github.com/redhat-et/ripwire) | 2026-07-29 | v0.7.0 (2026-11-23) | C++23 code-map/call-graph CLI + MCP; not a grep backend |
| [noahdunnagan/fsearch](https://github.com/noahdunnagan/fsearch) | 2026-10-08 | v0.2.2 (2026-11-12) | macOS whole-disk name + indexed content grep |
| [uutils/grep](https://github.com/uutils/grep) | 2026-05-27 | 0.2.0 (2026-08-27) | Rust GNU grep clone |
| ngi, trigrep, xgrep, fastripgrep, instantgrep | 2026-03 | various | Trigram/sparse n-gram clones inspired by [Cursor's post](https://cursor.com/blog/fast-regex-search) (2026-03-23); under 50 stars each |
| [ripgrep-rs](https://pypi.org/project/ripgrep-rs/) (PyPI) | fork | 0.4.5 (2026-11-23) | Native Python ripgrep binding; fork of the 2025 `python-ripgrep` |

## Python and Node Bindings for ripgrep (verified on PyPI/npm)

| Package | Kind | Latest | Status |
| --- | --- | --- | --- |
| `ripgrep-rs` (PyPI) | PyO3 binding over ripgrep crates; `search()`, `files()` | 0.4.5 (2026-11-23), Python 3.12+, free-threaded wheels | Active, but a 3-star fork (`phil65/python-ripgrep` ← `indent-com`); returns whole results, with no streaming or cancellation API in the README |
| `python-ripgrep` (PyPI) | same lineage | 0.0.9 (2025-07-30), Python <3.13 | Stale |
| `ripgrepy` (PyPI) | subprocess wrapper | 2.2.0 (2025-07-11) | Usable, low value over `subprocess` |
| `pyripgrep` (PyPI) | subprocess wrapper | 0.21 (2022) | Stale |
| `ripgrep-python` (PyPI) | native binding | 0.1.0 (2025-08-11, only release) | Abandoned-looking |
| `rgpy` (PyPI) | Rust regex/PCRE2 line scanner | 0.2.4 (2025-06-24), macOS arm64 wheel only | Not portable |
| `ripgrep` (PyPI) | rg binary wheel | 15.1.0 (2026-05-24) | Third-party publisher per attestation (see above) |
| `ripgrep-bin` (PyPI) | rg binary wheel | 16.0.0 (2026-11-23) | Third-party repack, many platforms |
| `@vscode/ripgrep` (npm) | per-platform binary packages | 1.18.0 (2026-05-07), rg 15.0.0 | Maintained by Microsoft |
| `ripgrep` (npm, pithings) | rg as embedded WASM | 0.3.1 (2026-04-06) | Interesting for no-native installs; performance UNVERIFIED |

## Backend Comparison for a Pluggable Keyword Provider

Context: the Metabrowser server is Python and already maintains a live inventory of up to
500,000 non-gitignored files with `catalog.change` events. The plan requires bounded,
cancellable, streaming text search with path, line, column and excerpt results. It
excludes requiring a database, external daemon or native extension, and it says rg cannot
be assumed to be installed.

| Criterion | ripgrep (subprocess) | ugrep (subprocess) | qmd BM25 | Zoekt | tantivy (tantivy-py) | SQLite FTS5 trigram (stdlib) | tgrep | fff-search |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Index | none | none (optional) | SQLite FTS5 | trigram shards | inverted index | inverted trigram | trigram + server | in-memory + watcher |
| Query latency | O(bytes) per query; ~tens of ms at repo scale warm, seconds at monorepo scale | similar, cold-FS gains with index | ~1 s per 5 queries in 2026-05 (process start dominated) | ms, sublinear | ms | ms for selective trigrams; poor for 1–2 char queries | ms warm (vendor) | ms warm (vendor) |
| Freshness | always current | always current; index "safe" | manual `qmd update` | re-index shards | app-driven | **app-driven from inventory events** | watcher, async lag | watcher |
| Ranking | none (path order or unordered) | none (`--sort=best` for fuzzy) | BM25 per document | code signals / BM25 option | BM25 | BM25 (`bm25()`) | none | frecency + fuzzy |
| Result granularity | line + byte offsets + submatches | line + column + offset | document + snippet | line, chunk | document/field | row (document or chunk) + snippet | line (rg JSON) | line |
| Streaming | JSONL | array/format | no (JSON array) | gRPC stream | iterator in-process | cursor in-process | JSONL | pages |
| Scoping to subtree/file set | paths, globs, `--in0` | paths, globs, argv | collections/metadata only | `file:` regex | queries on a path field | SQL WHERE/JOIN | paths/globs | `paths`/`globs` |
| Cancellation | kill process (clean) | kill process | kill process | RPC cancel | in-process | `interrupt()` | kill / RPC | in-process |
| New dependency | optional binary (2.2 MB) | optional binary (built from source on Linux) | Node 22 + native modules | Go service | native wheel | **none** | optional binary (6.7 MB) | native wheel |
| Disk/RAM | none | none / index files | ~2.3x corpus in the 2026-05 example | ~3.5x corpus | UNVERIFIED | UNVERIFIED (measure) | up to 3x during build | RAM |

Readings:

1. **No-index scan (rg) is the right first provider.** It is always fresh, has the best
   machine interface, and costs nothing when unused. rg 16's `--in0` lets the server pass
   the exact candidate list (a selected folder set, treemap selection, or inventory-
   filtered list) without argv limits. The provider must cap total results, truncate
   excerpts, and kill the process. VS Code already does exactly this.
2. **ugrep** adds fuzzy and Boolean modes but its JSON is not JSON Lines, it carries no
   context, and Linux needs a source build. It fits a power-user option, not the default.
3. **qmd BM25** is a docs-ranking tool, not a content grep. It works at document
   granularity, needs explicit collection setup and `qmd update`, and has no path-prefix
   filter in the CLI. It fits a separate "ranked docs" provider.
4. **Zoekt** solves multi-repository scale with a 3.5x index and a Go service. That is
   too heavy for a local file browser unless the user already runs it.
5. **FTS5 trigram through Python's `sqlite3`** fits evidence-gated Phase 4 best: it adds
   no dependency, scopes in SQL, offers BM25 and snippets, and the existing inventory can
   keep it fresh. Costs to measure: index size, build time, the minimum three-character
   query, and regex support (only via a prefilter plus verification).
6. **tantivy-py** is the scalable BM25 alternative if FTS5 index size or ranking falls
   short. **tgrep** and **fff** are worth benchmarking as "indexed grep" references, but
   both bring their own watcher, which duplicates Metabrowser's inventory.

## What the Benchmark Agent Should Measure

- Cold (dropped page cache, if permitted) and warm latency for a literal, a case-
  insensitive literal, a regex with a literal prefix, a regex without literals, and a
  multi-term OR. Use two corpora: a mid-size repo (~10k files) and a large tree (~100k+
  files).
- Time to first result versus total time, which matters for streaming UIs. Measure rg
  `--json` time-to-first-byte against `--sort=path`.
- Peak RSS; for indexed tools, index build time, index size relative to corpus, and
  incremental update time after touching 1 file and 1,000 files.
- Output bytes per result in plain, `--json`, `--json -C2`, and `-l`/`-c` modes; tokens
  per result for agent use.
- Bounded search: time to the first 100 results with caller kill (rg) versus native caps
  (`--max-results` in tgrep, `--max-files` in ugrep).
- Scoping cost: `--in0` with 10, 1,000 and 50,000 paths versus a directory argument.
- Cancellation latency: time from SIGTERM to exit during a large scan.

## Changes Since May 2026

- ripgrep 15.1.0 → 15.2.0 (2026-07-15) → **16.0.0** (2026-11-22): `--in/--in0`,
  `--glob-not`, `--max-bytes`, `RIPGREP_THREADS`, multiline JSON fix; grep crates and
  `ignore` 0.4.35 released the same day; `regex` 1.13.2 (2026-11-19).
- ugrep 7.8.2 → 7.8.5: DFA memory caps, encoding fixes.
- ast-grep 0.42.3 → 0.51.3: `outline`, `sg` deprecated, Zig/Markdown, ESQuery selectors,
  musl binaries.
- semgrep 1.187.0; **opengrep 2.0 removed Python** and added interfile taint.
- comby: OCaml 5 port and PCRE → `re` on master, no release. srgn returned with 0.14.3
  and 0.14.4. tree-sitter 0.26.9 → 0.27.2.
- fd 10.4.2 → 10.5.2; fzf 0.72/0.73 → 0.75.0 (performance and security fixes); skim 4.6 →
  5.9; television quiet after 0.15.9.
- **Google codesearch archived.** Zoekt added `zoekt-local-sync`. Hound saw only
  maintenance.
- **New:** microsoft/tgrep, greeg, xerj, zvec-grep, ripwire, fsearch, uutils/grep, and
  several trigram clones; fff grew Python and C SDKs (v0.11.0).
- qmd 2.5.x → 2.9.0: faster, exact collection-scoped BM25; metadata filters; HTTP
  `/search`; shared lock.
- src-cli 7.3.0 → 8.2.0; gh 2.106.0, and `gh search code` still uses the legacy engine.
- tantivy 0.26.1 → 0.27.0 crate; tantivy-py 0.27.0; tantivy-cli unchanged.
- SQLite 3.53.x → 3.54.1. Vectorscan 5.4.14.
- `@vscode/ripgrep` 1.18.0 (2026-05-07, rg 15.0.0). New PyPI rg binary wheels: `ripgrep`
  (third-party publisher) and `ripgrep-bin` 16.0.0.

## Open Questions / UNVERIFIED

- ugrep JSON byte sizes and exact `--json` behavior with `-A/-B/-C`. The note relies on
  README text; no local ugrep build.
- ast-grep: whether `-C` context appears in `--json=stream` output (the `lines` field
  covers only the match lines in the probe).
- tgrep: explicit file-list input, whether `--json` context matches rg byte for byte, and
  real index size ratios. The Copilot CLI integration claim was not checked.
- probe and cs: whether JSON output streams (cs has `-f json`; ranking implies end-of-scan output, not tested).
- rga: `--json` passthrough and license (GitHub reports NOASSERTION; believed AGPL-3.0
  from memory).
- livegrep and ack license strings (GitHub NOASSERTION); Hound API parameter names.
- ugrep index file format and location.
- Index size ratios for codesearch, tantivy and FTS5 trigram on code; to be measured.
- The `hyperscan` PyPI package's compatibility with Vectorscan.
- semgrep's built-in MCP server (not checked in this pass).
- The xerj and zvec-grep star counts (21.5k and 4.4k in under five months) are unusual;
  adoption is unverified.
- The archive date of google/codesearch: the API only reports `archived: true`; the last
  commit was 2026-08-30.
