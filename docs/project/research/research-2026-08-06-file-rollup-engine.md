# Research: High-Performance File Roll-Up Engine (Rust Library, CLI, and Python Embedding)

**Date:** 2026-08-06 (last updated 2026-08-06)

**Author:** Metabrowser project, with Claude Code research assistance

**Status:** In Progress

## Overview

Metabrowser’s core value is instant, always-fresh insight into large directory trees:
sizes, counts, modification times, file types, and per-file details, rolled up
hierarchically so that any directory can answer “what is in here, how big is it, what
changed recently, and what kinds of files live here?”

Today this is implemented in pure Python: an async BFS walker over `os.scandir`, an
in-memory `InventoryIndex` with incremental per-directory aggregates, and a
`watchfiles`-based watcher.
It works well but has a measured ceiling of roughly 7,000 files/second on a local SSD
(500k files take ~70 seconds to index), a hard cap of 500,000 files, and no persistence:
every server start pays the full walk again.

This research explores a from-the-ground-up Rust engine — “something like
[dust](https://github.com/bootandy/dust), but finer-grained and embeddable” — that would
provide:

- **Very fast tree walks** (parallel, syscall-efficient, gitignore-aware).
- **A persistent incremental cache** in the spirit of flowmark-rs’s incremental cache,
  so a re-run over a large tree touches only files modified since the last run and
  serves full results near-instantly.
- **An extensible set of tallies and roll-ups** at every level of the directory
  hierarchy: usage (bytes, counts), modification times, file types, and future
  content-derived metrics (paragraphs, words, sentences, lines) — each rolled up along
  its dimension hierarchically.
- **Pluggable file-type recognition** driven by declarative rules that generalize
  extension maps and magic sniffing.
- **Three consumption surfaces from one core**: a Rust library, a CLI (for testing,
  scripting, and agent use), and a Python embedding that metabrowser can call
  in-process, packaged so `uv add` just works.

The decision this research supports: whether to build this engine, what architecture and
cache design it should use, and how it should be embedded in metabrowser without
breaking the consumer-agnostic core and plugin boundary.

## Questions to Answer

1. How does metabrowser compute file roll-ups today, and where are its measured limits?
2. How do dust and similar tools (du, ncdu, dua, pdu, diskus, gdu) work internally, and
   what contributes to their performance?
3. How does flowmark-rs’s incremental cache achieve ~23 ms warm re-runs, and which parts
   of that design transfer to a file-metadata engine?
4. What do the strongest prior systems for “instant answers over large trees”
   (Everything, Watchman, git’s status machinery) teach about cache and revalidation
   design?
5. What are the shortcomings of each of these tools relative to metabrowser’s needs, and
   how could a new engine improve on them?
6. How should tallies and roll-ups be modeled so new metrics can be added without
   reworking the engine?
7. How should file-type recognition be structured so rules are declarative, prioritized,
   and pluggable — generalizing magic-style sniffing?
8. What is the right way to embed the engine in Python (in-process bindings vs.
   subprocess), and how is it packaged for uv?

## Scope

**Included:**

- Source review of dust 1.2.4 and flowmark-rs 0.3.2 (checked out under `attic/`), and of
  metabrowser’s walker/inventory/tree/watcher pipeline.
- Background on the wider tool landscape from documentation and general knowledge:
  du/ncdu/dua/pdu/diskus/gdu, Windows Everything, Watchman, git’s index caches,
  ripgrep’s `ignore` crate, jwalk, libmagic, shared-mime-info, and GitHub Linguist.
- Architecture, data model, cache, and packaging design for a new Rust engine.

**Excluded:**

- Implementation. This document proposes; a follow-up plan spec would schedule build
  phases and benchmarks.
- Full-text search and content indexing (see the separate scalable-file-search spec,
  `docs/project/specs/active/plan-2026-07-17-scalable-file-search.md`). The engine
  should leave room for it but this research does not design it.

## Findings

### How Metabrowser Rolls Up File Information Today

The current pipeline has four layers, all pure Python (the only native code involved is
`watchfiles`, itself a Rust-backed package):

- **Walker** (`src/metabrowser/walker.py`): an async BFS over `os.scandir`, one syscall
  batch per directory, never following symlinks.
  It yields `FsEntry` records and finalizes directories post-order, cascading
  `total_files`, `total_size`, and `newest_mtime_ns` up to the root.
  Directories within `first_render_depth` (2) are walked first so the UI paints quickly.
  Caps: `INVENTORY_MAX_FILES = 500_000`, `max_depth = 20`.
- **Inventory** (`src/metabrowser/inventory.py`): the in-memory `InventoryIndex`, keyed
  by relative path, maintaining incremental per-directory aggregates (descendant file
  counts and sizes, per-parent newest-mtime heaps) and per-path generation counters so
  stale walker writes never overwrite fresher watcher observations.
- **Tree and views** (`src/metabrowser/tree.py`, `recent.py`): `/api/tree` is served
  from the inventory with zero filesystem access once populated; before that, a
  recursive scandir path with TTL-cached subtree summaries (60 s) and a TTL-cached
  gitignore checker (parsing all `.gitignore` files costs ~1.5 s on large roots).
- **Watcher** (`src/metabrowser/watch_backends.py`): `watchfiles.awatch` with backend
  selection by filesystem type (native inotify/FSEvents on local filesystems, polling on
  NFS/FUSE). Events flow through the inventory into an SSE bus with bounded queues.

The per-file record (`FsEntry` in `events.py`) already carries the fields a roll-up
engine needs: relative path, parent, name, compound-tail extension (`derive_ext` folds
`archive.tar.gz` to `.tar.gz`), classified `kind`, size, `mtime_ns`, an mtime-based
fingerprint, activity flag, per-kind view list, labels, gitignored flag, and — for
directories — `total_files`, `total_size`, `newest_mtime_ns`.

File-type recognition is layered and already pluggable:

- Static extension sets (`file_extensions.py`) for browser-text, image, and trackable
  types.
- A registered detector chain (`file_kinds.py`) with content-aware detectors (e.g. JSONL
  adapter sniffing) and a `VIEW_REGISTRY` mapping kinds to view tabs.
- Declarative plugin rules (`plugin_loader/classify.py` + `manifest.toml` `[[kind]]`
  blocks) compiled into a priority-sorted classifier.
  Predicates include extensions, basenames, folder markers, path globs, JSONL adapter,
  YAML frontmatter keys, and bounded JSON/YAML top-level inspection (capped reads of 256
  KiB / 16 KiB).

**Measured limits and known concerns:**

- Walker throughput is ~7,000 files/s on Linux ext4 SSD (per `settings.py` comments):
  500k files ≈ 70 s, longer on FUSE/NFS. The 500k cap exists to bound memory and time.
- No persistence: every server start re-walks everything.
  The scalable-file-search spec explicitly defers “persistent metadata” and “native
  extensions” until measurements demand them — this research is the groundwork for that
  decision.
- Gitignore matching had to be special-cased (children of ignored dirs inherit the flag)
  because per-entry pathspec matching “dominates walker time” at 500k files.
- TODO.md calls for explicit time/memory/item-count budgets for directories with
  hundreds of thousands of entries, and for scalable search with optional persistent
  indexing.

The important architectural fact: metabrowser already has clean seams.
The walker yields a well-defined record stream; the inventory consumes it; plugins
consume classification and projections through a documented API. A Rust engine can slot
in at the walker/inventory seam without disturbing the plugin boundary.

### Dust: How It Works and Why It Is Fast

Dust (`attic/dust`, v1.2.4, ~2,600 lines of Rust) is a `du` replacement that prints a
tree of the largest items with percentage bars.

**Architecture** (`src/dir_walker.rs`, `src/node.rs`, `src/platform.rs`):

- A recursive walk where each directory’s `read_dir` iterator is bridged into rayon
  (`par_bridge`) so subdirectories are walked by the thread pool.
  A source comment notes that naive recursion through rayon cost 3x; they hand-unravel
  one level to keep the pool busy.
- Each entry becomes a `Node { name, size, children, inode_device, depth }`. Metadata
  comes from one `symlink_metadata` call per entry: apparent size or allocated blocks (×
  512), inode + device, and mtime/atime/ctime.
- A post-pass (`clean_inodes`) deduplicates hardlinks via a `(inode, device)` hash set,
  sorts children by inode (cheaper than by name), and sums sizes bottom-up into each
  directory node.
- Progress reporting uses relaxed atomics polled by a spinner thread; errors accumulate
  in a mutex-guarded set; interrupted syscalls retry with a bounded cap.
- Platform quirks are handled in one place: 512-byte block conventions, NTFS block-count
  overcounting capped by blksize-derived bounds, Windows compressed/sparse sizes via a
  separate crate.

**What contributes to its performance:**

- **Parallelism saturates the syscall path.** The walk is metadata-only (`getdents` +
  `statx` per entry, no content reads), and rayon keeps many directories in flight, so
  it is bounded by kernel/filesystem latency, not CPU. This is the same lesson as
  diskus, dua (jwalk), and pdu: parallel walkers gain large factors over serial `du` on
  SSDs, especially with warm page cache.
- **Small, flat data.** One `u64` size per node, no string re-allocation beyond the
  path, inode-based sorting, release profile with `lto = true` and `codegen-units = 1`.
- **Bounded extra work.** Filters (regex, mtime/atime/ctime windows, filesystem
  allowlist) short-circuit when unused; a comment marks this as measurable.

**Feature surface relevant here:** `--filecount` (count instead of bytes), `--filetime`
(newest time instead of bytes), `--file-types` (whole-tree tally by extension),
`--output-json`, min-size, depth limits, ignore lists, `--files0-from`, and
mtime/atime/ctime filter expressions.

**Shortcomings for our use case:**

- **No cache of any kind.** Every invocation re-walks the entire tree.
  Dust is a one-shot renderer; “instant on re-run” is out of scope for it.
- **One number per node.** `size` is a single `u64` that is *reused* to mean bytes, or
  file count, or newest filetime depending on mode — the modes are mutually exclusive.
  There is no metric vector, so you cannot get sizes, counts, and newest mtimes in one
  walk, let alone per-type tallies per directory.
- **Tallies are not hierarchical along dimensions.** `--file-types` aggregates the whole
  tree by extension; there is no per-directory type breakdown.
- **Binary only.** The crate exposes no library API; consuming it means shelling out and
  parsing output. JSON output exists but reflects the display tree (post
  filtering/depth-trimming), not a full inventory.
- **Metadata is discarded.** mtime/atime/ctime are read for filtering but not retained
  in nodes or output.
- **No gitignore awareness** (only explicit ignore lists), no file-kind recognition
  beyond extension string, no watch mode.

None of these are flaws in dust — they are scope.
But they define exactly the gap a new engine would fill: retain the walk performance,
replace the display-oriented single-metric tree with a cached, multi-metric, queryable
inventory.

### Flowmark-rs: The Incremental Cache Model

Flowmark-rs (`attic/flowmark-rs`, v0.3.2) formats Markdown; its relevance here is its
incremental cache and its packaging.
Design notes live in `docs/cache.md` and the completed spec
`docs/project/specs/done/plan-2026-02-27-incremental-cache-and-performance-roadmap.md`
in that repo.

**How the cache works** (`src/incremental_cache.rs`):

- The unit of caching is a **content hash set**: a `u64` hash of file bytes is either in
  the “known formatted” set or not.
  On a hit, formatting is skipped entirely.
- Manifests are **project-scoped**: one TOML file per project root, at
  `<user-cache-dir>/flowmark/incremental/<hash-of-canonical-root>.toml`.
- The whole manifest is **invalidated by a formatter fingerprint**: a hash of binary
  version + all formatting options + config file path and bytes.
  Change anything that could change output, and the cache silently rebuilds.
  Corrupt manifests are treated as empty, not errors.
- Writes are **atomic** (temp file + rename), and the flush unions the read set with the
  write set so warm entries survive runs that touch few files.
- The CLI shares the cache across a rayon `par_iter` over files discovered by ripgrep’s
  `ignore::WalkBuilder` (gitignore-aware parallel discovery).

**Measured results** (from flowmark-rs `benchmarks/REPORT.md`, 928-file / 23 MB corpus):
fresh run 0.71 s parallel; warm cached re-run **0.023 s**; the Python flowmark on the
same corpus: ~48 s. Warm re-runs are ~30x faster than fresh, and the Rust/Python gap is
60–130x. This is the UX bar: warm runs in tens of milliseconds.

**What transfers, and what does not:**

- Transfers directly: user-cache-dir resolution order, project-root-scoped manifests,
  fingerprint-based whole-cache invalidation (engine version + config), atomic
  persistence, corrupt-cache-equals-empty, and cache lifecycle UX (`--show-cache`,
  `--clear-cache`, `--no-cache`).
- Does **not** transfer: the content-hash model itself.
  Flowmark must read every file’s bytes anyway (it cannot know a file is formatted
  without reading it), so hashing content is free.
  A metadata engine’s entire goal is to *avoid* reading content; its cheap invalidation
  signal is the stat fingerprint (size, `mtime_ns`, inode), with content hashing
  reserved for the optional content-metric tier.
  Metabrowser already uses exactly this fingerprint style in `MtimeCache`
  (`strif.file_mtime_hash`), and git’s index has used stat fingerprints for decades.
- Packaging: flowmark-rs publishes to PyPI via **maturin with `bindings = "bin"`** — the
  wheel ships the native CLI binary as a Python entry point, no PyO3 involved.
  That is one of two viable embedding models (see below).

### The Wider Landscape: Instant Answers Over Large Trees

**Serial walkers (du, ncdu):** one thread, one stat at a time; fine for cold small
trees, minutes for millions of entries.
ncdu can export/import a scan as JSON — an ad-hoc snapshot, but with no invalidation
story (re-import shows stale data).

**Parallel walkers (dust, dua, pdu, gdu, diskus):** all converge on the same design —
work-stealing thread pool over directories, stat-only traversal.
diskus is the minimal proof: it computes just the total and is roughly an order of
magnitude faster than serial `du` on SSDs.
dua adds an interactive TUI and uses jwalk (parallel walkdir with ordered per-directory
results). All of them rescan from zero every run.

**Windows Everything:** the benchmark for “instant.”
It does not walk at all: it reads the NTFS Master File Table directly to build its index
in seconds, then consumes the NTFS USN change journal for real-time incremental updates.
Lessons: (1) index once, then apply a change feed; (2) a persisted index makes queries
independent of tree size.
Limitation: deeply filesystem-specific and Windows-only; nothing portable gives
MFT-grade enumeration, and only some platforms have replayable journals.

**Watchman:** a persistent daemon that crawls once, subscribes to OS notifications
(FSEvents/inotify), and serves queries with a **clockspec** — “give me everything
changed since clock C.” This is the strongest portable architecture for freshness, and
its `since`-query model is worth copying at the API level.
Costs: a daemon dependency, socket protocol, and operational complexity — heavier than
metabrowser wants to impose.
(Metabrowser already has its own watcher; the engine should integrate with it, not ship
a daemon.)

**Git’s status machinery:** the closest widely-deployed prior art for our cache tier:

- The index stores per-file stat fingerprints (size, mtimes, inode/dev) and treats a
  matching fingerprint as “unchanged” without reading content (with “racily clean”
  handling for same-second mtimes).
- The **untracked cache** records per-directory mtimes and skips re-listing directories
  whose mtime is unchanged — valid because directory mtime changes when entries are
  added/removed/renamed.
  (It cannot detect *content* changes of existing files; git covers those with the
  per-file fingerprints.)
- **fsmonitor** (Watchman hook or the builtin daemon) upgrades this to
  notification-driven invalidation.

This three-tier structure — per-file stat fingerprints, per-directory listing cache,
optional watcher acceleration — is precisely the shape a portable roll-up cache should
take.

**Walker building blocks in Rust:** ripgrep’s `ignore` crate provides a parallel,
gitignore-aware walker (flowmark-rs and fd use it); `jwalk` provides parallel walks with
ordered results; `rayon` underlies both.
A new engine composes these rather than reinventing the pool.

### File-Type Recognition Landscape

Four families of prior art:

- **Extension maps:** `mimetypes` (Python), `mime_guess` (Rust), and metabrowser’s
  extension sets. Fast, zero I/O, wrong for extensionless or misnamed files.
- **Magic sniffing:** libmagic (the `file` command) evaluates a compiled database of
  offset/type/value tests; XDG **shared-mime-info** is the cleaner modern form —
  declarative XML rules combining globs (with weights) and magic byte tests (with
  priorities), plus a `sub-class-of` type hierarchy.
  Rust ports exist (`tree_magic_mini`), as do hardcoded-signature crates (`infer`).
- **Language classification:** GitHub Linguist (and its Rust port hyperpolyglot) layers
  strategies in cost order: filename → extension → shebang → editor modeline → content
  heuristics (regexes) → Bayesian classifier, stopping at the first unambiguous answer.
- **Metabrowser’s own manifests:** the `[[kind]]` TOML rules already generalize this
  locally — extensions, basenames, folder markers, globs, adapter sniffing, and bounded
  frontmatter/JSON/YAML inspection, with priorities.

The synthesis is clear and validates the direction metabrowser has already taken:
**recognition should be a priority-ordered cascade of declarative rules, evaluated
cheapest-first, with content tests bounded and optional.** The improvement a Rust engine
offers is making that cascade data-driven end to end (rules compiled to automata — glob
sets and Aho-Corasick magic matchers — instead of Python callables), so the same rule
files can be evaluated at walk speed for millions of files, and plugins can keep
contributing rules in the same TOML dialect they use today.

### What Actually Contributes to Performance (Synthesis)

Across all of these systems the cost model is consistent:

1. **The floor of a cold scan is one directory read per directory plus one stat per
   entry.** Nothing portable beats it (only MFT/journal tricks do).
   So a cold scan is won by parallelism (saturate the kernel), syscall discipline (use
   what `readdir` already returned; on Linux, `statx` with a narrow field mask), and
   small data structures.
   This is dust/diskus territory, and Rust reaches it; Python cannot — metabrowser’s 7k
   files/s is respectable *for Python* and roughly 10–50x from what parallel Rust
   achieves on the same hardware (flowmark measured 60–130x on CPU-bound work;
   stat-bound work gains less from the language but greatly from the parallelism the GIL
   prevents).
2. **The floor of a warm re-scan is a stat sweep — unless you persist and revalidate.**
   With a persisted snapshot, re-runs cost: load snapshot (one sequential read of a
   compact file, milliseconds) + revalidation (parallel stat sweep, with the dir-mtime
   shortcut skipping listing of unchanged directories) + re-derivation only for entries
   whose fingerprint changed.
   This is git’s model, and flowmark proves the UX (23 ms warm).
3. **Content work must be opt-in, lazy, and cached by fingerprint.** Reading bytes is
   orders of magnitude more expensive than statting.
   Every system that touches content (linguist heuristics, libmagic, flowmark,
   metabrowser’s bounded JSON/YAML probes) either bounds the read (first N KiB) or
   caches by content identity.
4. **A change feed converts re-scans into deltas.** Watcher events (or journals where
   they exist) let a long-lived process keep the snapshot hot continuously — which is
   exactly metabrowser’s server mode.
   A CLI one-shot instead revalidates on start.

## Key Insights

- **Dust and flowmark are complementary halves of the design.** Dust shows how to walk
  at hardware speed but keeps nothing; flowmark shows how to persist “work already done”
  and invalidate it safely but keys on content.
  The new engine is “dust’s walk + flowmark’s cache discipline, keyed on stat
  fingerprints, retaining a full multi-metric inventory instead of one display tree.”
- **The single-`u64` node is the deepest limitation to fix.** Dust’s mutually exclusive
  size/count/filetime modes all exist because a node holds one number.
  Model per-file records → metric vectors, and per-directory roll-ups as **monoid-style
  reducers** (sum, max, min, count, histogram, top-k, count-by-key), and every mode
  becomes one walk, incremental updates become “recompute ancestors of dirty nodes,” and
  extensibility becomes “register a reducer.”
- **Serve-stale-then-revalidate is the honest way to be “instant.”** Everything,
  Watchman, and git all answer from the index immediately and reconcile against the
  filesystem asynchronously.
  The engine should load the snapshot, answer, and stream revalidation deltas — the same
  two-phase pattern metabrowser’s UI already has (first-paint depth-2, then deepen).
- **Metabrowser’s plugin classification dialect is a good seed for the rules format.**
  Its `[[kind]]` predicates are a practical superset of shared-mime-info globs and a
  subset of linguist’s cascade.
  Compiling (a subset of) that dialect in Rust keeps one rule language across engine and
  plugins, preserving the plugin boundary.
- **Python is the integration layer, not the hot path.** The scalable-file-search spec’s
  instinct to defer native code until measured is sound — and the measurements now
  exist: 70 s cold walks at the cap, ~1.5 s gitignore parsing, per-request full-index
  scans for the recent view.
  Those are the hot paths a native engine removes; everything above the inventory seam
  (routes, projections, plugins, SSE) stays Python.

## Proposed Architecture

One Cargo workspace, three surfaces over one core (mirroring flowmark’s feature-gated
layout):

```
rollup-core   (lib: walker, snapshot store, revalidator, reducers, type rules)
rollup-cli    (bin: human tree output à la dust + stable JSON/JSONL; testing, agents)
rollup-py     (PyO3 cdylib: in-process API for metabrowser; abi3 wheels via maturin)
```

### Data Model

- **File record** (superset of dust’s `Node`, aligned with metabrowser’s `FsEntry`):
  interned parent path + name, kind (file/dir/symlink), size, allocated blocks,
  `mtime_ns` (+ ctime), inode/device, flags (hidden, gitignored, symlink), compound
  extension, resolved file type id.
- **Metrics as reducers.** A metric declares: id, version, input tier (stat-only vs.
  content), and a commutative merge.
  Built-in stat-tier metrics: total bytes, allocated bytes, file/dir counts,
  newest/oldest mtime, mtime-recency histogram, size histogram, count-and-bytes by file
  type, top-k largest, top-k most recent.
  Content-tier metrics (later): line/word/sentence/paragraph counts per document type,
  delegated to pluggable analyzers.
- **Hierarchical roll-ups.** Every directory node stores the merged reducer state of its
  children; queries read them directly ("tally by type under `src/` at depth 2", “newest
  mtime under any node”) with no walking.
  Incremental updates re-merge only the ancestor chain of changed entries — the same
  shape as metabrowser’s `_update_ancestor_aggregates`, but over arbitrary registered
  metrics.

### Cache and Revalidation (Three Tiers, Git-Shaped)

1. **Snapshot.** The full inventory + roll-up state persisted per root under the user
   cache dir, keyed by hash of canonical root (flowmark’s layout), in a compact binary
   format (e.g. postcard/bincode, optionally zstd) with a format version and an **engine
   fingerprint** (engine version + config + rule-set hash) that invalidates wholesale on
   mismatch — flowmark’s discipline exactly.
   Atomic temp-file + rename writes; corrupt = empty.
   Target: load in low milliseconds for 500k entries (tens of MB).
2. **Revalidation.** On open: a parallel sweep comparing stat fingerprints (size,
   `mtime_ns`, inode) against the snapshot.
   Directories whose own mtime and entry list are unchanged skip re-listing (the
   untracked-cache trick); files with unchanged fingerprints keep their derived data
   (type verdicts, content metrics) with zero reads.
   Only changed entries re-derive.
   Results stream as deltas so callers can serve the stale snapshot instantly and
   reconcile.
3. **Watch mode.** In a long-lived process (the metabrowser server), a `notify`-based
   watcher (or events fed in from the host’s existing watcher) marks dirty paths and the
   engine incrementally restats and re-rolls just those subtrees, keeping the snapshot
   perpetually warm and flushing it periodically.
   A Watchman-style `since(clock)` query API exposes deltas to consumers.

Content-derived data (type-sniff verdicts requiring reads, word counts, etc.)
caches by `(stat fingerprint, analyzer id, analyzer version)` — flowmark’s
fingerprint-invalidation idea applied per-analyzer instead of whole-cache.

### File-Type Recognition Engine

- Rules are data: a TOML dialect deliberately compatible with metabrowser’s `[[kind]]`
  manifests — extension/basename/glob/folder-marker predicates plus bounded content
  probes (magic bytes, shebang, frontmatter/JSON/YAML keys) — with priorities and a
  category hierarchy (text/binary, media class, format family, à la shared-mime-info
  `sub-class-of`).
- Compiled once per run into fast matchers (extension hash maps, glob sets, Aho-Corasick
  magic tables); evaluated cheapest-first with content probes only when cheap tiers are
  ambiguous *and* the caller asked for content-level confidence.
- Ships with a standard rule set (generalizing metabrowser’s built-ins and the common
  libmagic/linguist cases); consumers and plugins layer additional rule files on top.
  Python-side detectors that need arbitrary logic still run in Python, downstream of the
  engine’s verdict — the engine’s verdict is a hint plus category, not a cage.

### Python Embedding and uv Packaging

Three viable models, in increasing coupling:

- **A. Binary wheel + subprocess (the flowmark-rs model, maturin `bindings = "bin"`).**
  Simplest; total version-skew isolation; JSON/JSONL over stdout.
  Costs process spawn (~ms) and serialization per call; no shared watch state.
  Right for CLI-shaped and agent use, wrong as metabrowser’s primary path — the server
  wants a persistent in-process index it can query per-request.
- **B. PyO3 cdylib (maturin abi3 wheels).** In-process module; the engine owns a
  background thread pool + watcher, releases the GIL during native work, and exposes:
  `open(root, config) -> Index`, `index.query(...)` (tree/tallies/top-k/recent),
  `index.since(clock)`, `index.refresh()`, `index.entries(...)` as dicts or typed
  objects. abi3 keeps the wheel matrix small (one wheel per OS/arch covering all CPython
  versions); uv consumes and builds maturin projects natively.
- **C. Both from one workspace** — the recommendation.
  The CLI and the Python module are thin frontends over `rollup-core`; the CLI doubles
  as the agent surface and the debugging surface (dust-style tree + `--json`), mirroring
  how metabrowser’s `walk.py` CLI reproduces `/api/tree` today.
  Metabrowser depends on the wheel like any other locked dependency (subject to the
  supply-chain cool-off policy; first-party crates/wheels can be pinned exactly as
  flowmark-rs is today).

Integration seam in metabrowser: the engine replaces the walker + inventory hot path
(cold boot walk, aggregates, recent/tree queries, gitignore evaluation), emitting the
same record stream `InventoryIndex` consumes today — or eventually backing it entirely —
while the SSE bus, projections, plugin API, and classification-dependent views stay
untouched. `watchfiles` events can be fed into the engine, or the engine’s own watcher
can replace that path server-side.

### Agent Skill Angle

Because warm queries are milliseconds, agents can call the CLI freely: “tally this tree
by type,” “top 20 largest,” “what changed in the last hour,” “full JSON inventory of
this subtree.” A small skill (like `skills/metabrowser`) would document the CLI with
`--help` as the source of truth.
This gives agents instant tree insight without spawning a server, and gives the engine a
second consumer that keeps the CLI honest.

## Comparison Matrix

| Criterion | du/ncdu | dust | dua/pdu/diskus | Everything | Watchman | git status | metabrowser today | Proposed engine |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Parallel walk | no | yes (rayon) | yes | n/a (MFT) | crawl once | partial | no (async, GIL) | yes (rayon/ignore) |
| Persistent cache | no (ncdu: manual export) | no | no | yes | yes (daemon) | yes (index) | no | yes (snapshot) |
| Incremental revalidation | no | no | no | journal | notifications | stat fingerprints + untracked cache | watcher (in-memory only) | fingerprints + dir-mtime + watcher |
| Warm-run cost | full walk | full walk | full walk | ~0 | ~0 | stat sweep | 0 while running; full walk on restart | snapshot load + stat sweep (or ~0 in watch mode) |
| Metrics per node | 1 | 1 (mode-switched) | 1 | metadata index | file list | status only | fixed 3 (files/bytes/newest) | extensible reducer vector |
| Per-dir type tallies | no | no (global only) | no | query-side | query-side | no | no | yes |
| File-type recognition | no | extension display | no | extension | no | no | pluggable, Python-speed | pluggable, compiled rules |
| Library API | no | no | dua: partial | no | socket | libgit2 | Python-internal | Rust + Python + CLI |
| Python embedding | — | subprocess only | — | — | client lib | pygit2 | native | PyO3 wheel (uv) |
| Portable | yes | yes | yes | Windows/NTFS only | daemon required | yes | yes | yes |

## Options Considered

### Option A: Wrap Dust (or dua) as a Subprocess

**Description:** Shell out to dust `--output-json` (or dua) for size roll-ups.

**Pros:**

- Zero engine code to write; battle-tested walkers.

**Cons:**

- No cache: every call is a full rescan, so it solves the wrong problem.
- Display-shaped JSON, single metric, no type tallies, no mtime retention, no library
  API; would still need all the inventory/cache work built on top.

### Option B: Adopt Watchman

**Description:** Run Watchman as a sidecar; query it for file lists and changes.

**Pros:**

- Mature clockspec/subscription model; proven at scale.

**Cons:**

- Heavy operational dependency for a local-first tool metabrowser installs via uvx.
- Provides file lists and changes, not roll-ups, tallies, type recognition, or content
  metrics — the aggregation engine would still need building.

### Option C: Optimize the Python Path

**Description:** Persist `InventoryIndex` (e.g. SQLite/pickle), add multiprocessing for
the walk, keep everything in Python.

**Pros:**

- No new toolchain; incremental delivery inside the current codebase.

**Cons:**

- The GIL caps stat-sweep parallelism; multiprocessing adds serialization overhead
  comparable to the work saved.
- Revalidation sweeps and rule matching remain Python-speed (the gitignore and
  recent-view hotspots stay).
  The ceiling is maybe 2–3x, not 10–50x, and none of it is reusable outside metabrowser
  (no CLI/agent surface, no other consumers).

### Option D: Ground-Up Rust Engine (Recommended)

**Description:** The workspace described above: `rollup-core` + CLI + PyO3 wheel,
snapshot cache with stat-fingerprint revalidation, reducer-based roll-ups, compiled
declarative type rules.

**Pros:**

- Removes every measured hot path at once: warm-start server boots, instant agent
  queries, and materially lifting the 500k cap.
- Reusable: library, CLI, skill, and Python embedding from one core; useful beyond
  metabrowser.
- Cache discipline and packaging have a working exemplar (flowmark-rs) to copy.

**Cons:**

- A new codebase and CI matrix (Rust toolchain, wheel builds) to own.
- Rule-dialect compatibility with plugin manifests needs care to avoid drift.
- A native wheel dependency raises the supply-chain review bar (mitigated by it being
  first-party, like flowmark-rs).

## Recommendations

1. **Build Option D as a standalone repo** (working name: e.g. `rollup-rs`), starting
   with `rollup-core` + CLI only: parallel gitignore-aware walk, stat-tier reducers
   (bytes, counts, mtimes, per-type tallies, top-k), snapshot + revalidation cache,
   dust-style tree output plus stable JSON. Benchmark against dust (cold) and against
   the flowmark warm-run bar (tens of ms on ~1k-file corpora; target well under 1 s warm
   for 500k entries).
2. **Add the PyO3 surface second**, once the snapshot format survives a few iterations,
   and integrate behind metabrowser’s walker/inventory seam as an optional accelerator
   (the pure-Python path remains the fallback, preserving the no-native-requirement
   stance of the search spec).
3. **Define the type-rule dialect early** as a compatible superset of the plugin
   `[[kind]]` predicates, so plugins never need two rule languages.
4. **Design queries around `since(clock)` deltas** from day one; it is cheap now and
   unlocks watch-mode and SSE integration later.
5. **Defer content-tier metrics** (words/sentences/paragraphs) until the stat tier is
   solid — but reserve their place in the reducer registry and the per-analyzer
   fingerprint cache now, since that shapes the snapshot format.

## Open Questions

1. Snapshot format: postcard/bincode vs.
   an mmap-friendly zero-copy layout (rkyv/flatbuffers)?
   Zero-copy helps the “load 500k entries in ms” target but complicates evolution;
   format-version invalidation makes evolution cheap either way.
2. Should the engine own gitignore semantics (the `ignore` crate) or take ignore rules
   as input from the host?
   Metabrowser tracks `gitignored` as a flag on entries rather than excluding them — the
   engine must support “walk everything, tag ignored” mode, which `ignore` does not do
   natively (it prunes).
   This may need a custom matcher pass.
3. How much of classification belongs engine-side?
   Proposal: the engine yields type/category verdicts from compiled rules; adapter-level
   sniffing (e.g. which agent wrote a JSONL) stays in Python plugins.
   Validate against real plugin manifests.
4. Hardlink/bind-mount dedup policy: dust’s `(inode, device)` set is global and
   order-dependent; for stable roll-ups the engine needs a deterministic attribution
   rule (e.g. count under the first path in sorted order, expose link count).
5. Watcher ownership in metabrowser: feed `watchfiles` events into the engine, or let
   the engine’s notify watcher replace that path?
   (This affects the NFS/polling fallback logic metabrowser already tuned.)
6. Where do bounded content probes cap out for type recognition (first 8 KiB?), and is
   sniffing on-demand-only at first (so the walk stays stat-pure)?

## Next Steps

- Review this document; decide go/no-go on Option D and the standalone-repo question.
- If go: draft a plan spec (`new-plan-spec`) for phase 1 (core + CLI + benchmarks), with
  beads for the walker, reducers, snapshot store, revalidator, type-rule compiler, and a
  benchmark harness (corpus generator mirroring flowmark’s
  `benchmarks/generate_corpus.sh`).
- Prototype the risk spikes first: snapshot load time at 500k entries for candidate
  formats, and “walk everything, tag ignored” on top of the `ignore` crate.

## References

- [dust](https://github.com/bootandy/dust) (source reviewed at v1.2.4, `attic/dust`)
- [flowmark-rs](https://github.com/jlevy/flowmark-rs) (source reviewed at v0.3.2,
  `attic/flowmark-rs`; see its `docs/cache.md` and incremental-cache spec)
- [diskus](https://github.com/sharkdp/diskus), [dua](https://github.com/Byron/dua-cli),
  [pdu](https://github.com/KSXGitHub/parallel-disk-usage),
  [gdu](https://github.com/dundee/gdu), [ncdu](https://dev.yorhel.nl/ncdu)
- [Everything: how it indexes NTFS](https://www.voidtools.com/faq/)
- [Watchman](https://facebook.github.io/watchman/)
- [git untracked cache](https://git-scm.com/docs/git-update-index#_untracked_cache) and
  [fsmonitor](https://git-scm.com/docs/git-fsmonitor--daemon)
- [ripgrep `ignore` crate](https://docs.rs/ignore), [jwalk](https://docs.rs/jwalk)
- [shared-mime-info spec](https://specifications.freedesktop.org/shared-mime-info-spec/latest/),
  [GitHub Linguist](https://github.com/github-linguist/linguist),
  [hyperpolyglot](https://github.com/monkslc/hyperpolyglot),
  [infer](https://docs.rs/infer), [tree_magic_mini](https://docs.rs/tree_magic_mini)
- [PyO3](https://pyo3.rs/), [maturin](https://www.maturin.rs/)
- Metabrowser internals: `src/metabrowser/walker.py`, `inventory.py`, `tree.py`,
  `watch_backends.py`, `file_kinds.py`, `plugin_loader/classify.py`, and
  `docs/project/specs/active/plan-2026-07-17-scalable-file-search.md`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
