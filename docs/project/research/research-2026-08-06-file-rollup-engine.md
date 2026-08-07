# Research: Frollup — a High-Performance File Roll-Up Engine (Rust Library, CLI, and Python Embedding)

**Date:** 2026-08-06 (last updated 2026-08-07)

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

This research explores a from-the-ground-up Rust engine — **fdu** — “something like
[dust](https://github.com/bootandy/dust), but finer-grained and embeddable,” that would
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
- **An optional watch layer**: sub-libraries that listen for filesystem changes and turn
  them into deltas that update the live in-memory roll-up structure and update or
  invalidate the on-disk cache — replacing work metabrowser currently does in Python.
- **Three consumption surfaces from one core**: a Rust library, a CLI (for testing,
  scripting, and agent use), and a Python embedding that metabrowser can call
  in-process, packaged so `uv add` just works.

The organizing idea that emerged from the research: fdu is really **three clean
artifacts and one contract**. An in-memory hierarchical index; a serialized snapshot of
that index; and a **delta API** that is the single way anything — the walker, the
watcher, the revalidator, or a snapshot journal — changes the index or the cache.
Get the delta contract right and the walk, watch, cache, and query layers become
separable libraries.

The decision this research supports: whether to build this engine, what architecture and
cache design it should use, and how it should be embedded in metabrowser without
breaking the consumer-agnostic core and plugin boundary.

This document reflects **three research passes**. The first compared metabrowser’s
current pipeline against dust and flowmark-rs.
The second broadened the survey to twelve tools across four languages and read their
source directly, on the principle that proven production techniques beat invented ones —
and changed several conclusions: dust turns out **not** to be the performance bar to
target, and the walk techniques that matter most are syscall-level ones dust does not
use. The third examined the watch layer: what filesystem-event backends can actually
guarantee (by reading notify and watchfiles, the exact stack metabrowser uses today),
and what that implies for a delta-driven design.

## Questions to Answer

1. How does metabrowser compute file roll-ups today, and where are its measured limits?
2. How do dust and similar tools (du, ncdu, dua, pdu, diskus, gdu, dut) work internally,
   and what contributes to their performance?
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
9. **What specific, proven syscall-level and concurrency techniques do the fastest tools
   use, in enough detail to reimplement?**
10. **Which of these codebases can we legally borrow designs from, and under what
    constraints?**
11. Should watching be part of the library family, and what can filesystem-event
    backends actually guarantee — per platform — for a consumer that wants to apply
    events as incremental deltas rather than as “go rescan” hints?
12. What should the delta contract look like so the same type drives in-memory updates,
    cache maintenance, and the consumer-facing change feed?

## Scope

**Included:**

- Direct source review of tools checked out under `attic/`: dust 1.2.4, flowmark-rs
  0.3.2, ncdu 1.15.1 (C), ncdu 2.x (Zig), dut, duc, bfs, fd, scc, tokei, fsearch, gdu,
  dua-cli, erdtree — plus, for the watch layer, the Rust `notify` crate workspace and
  `watchfiles` (the Python package metabrowser uses today, whose backend is notify).
- Review of metabrowser’s walker/inventory/tree/watcher pipeline.
- Background from documentation on systems not checked out: Windows Everything,
  Watchman, git’s index caches, plocate, borg/restic metadata caches.
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
  sorts children by inode (cheaper than by name), and sums sizes bottom-up.
- Platform quirks handled in one place: 512-byte block conventions, NTFS block-count
  overcounting capped by blksize-derived bounds, Windows compressed/sparse sizes.

**What contributes to its performance:** parallelism that saturates the syscall path,
small flat per-node data, and short-circuited filters.
Release profile uses `lto = true` and `codegen-units = 1`.

**Shortcomings for our use case:**

- **No cache of any kind.** Every invocation re-walks the entire tree.
- **One number per node.** `size` is a single `u64` *reused* to mean bytes, or file
  count, or newest filetime depending on mode — the modes are mutually exclusive.
  You cannot get sizes, counts, and mtimes in one walk, let alone per-type tallies per
  directory.
- **Tallies are not hierarchical along dimensions.** `--file-types` aggregates the whole
  tree by extension; there is no per-directory type breakdown.
- **Binary only.** No library API; consuming it means shelling out.
  Its JSON reflects the display tree (post filtering/depth-trimming), not a full
  inventory.
- **Metadata is discarded.** mtime/atime/ctime are read for filtering but not retained.
- **No gitignore awareness**, no file-kind recognition, no watch mode.

The second research pass added an important correction: **dust is not the tool to
benchmark against.** By its competitors’ published numbers it sits mid-pack, and the
techniques that separate the leaders from dust are exactly the ones described below.

### Dut: The Warm-Cache Champion, and the Roll-Up Technique to Steal

`dut` (`attic/dut`, C, single 1,547-line `main.c`, **GPL**) was the most valuable find
of the second pass. Its own benchmarks (whole-`/` scan, i5-10500h, warm cache) report:

| Tool | Mean | vs. dut |
| --- | --- | --- |
| **dut** | **779.7 ms** | 1.0x |
| pdu | 1.127 s | 1.45x |
| dust | 2.206 s | 2.83x |
| dua | 2.313 s | 2.97x |
| gdu | 2.927 s | 3.75x |
| du (coreutils) | 5.356 s | 6.87x |

These are the author’s own numbers on one corpus, so treat the ranking as indicative
rather than settled — but the techniques behind them are verifiable in the source, and
they are the ones that matter.

**Syscalls.** `dut` opens each directory with
`open(name, O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW)`, then loops on
`syscall(SYS_getdents64, fd, scratch, scratch_size)` with a **1 MB per-thread scratch
buffer reused across directories**. Metadata comes from
`statx(fd, dent->d_name, AT_SYMLINK_NOFOLLOW|AT_NO_AUTOMOUNT, STATX_BASIC_STATS, &sbuf)`
— relative to the directory fd, so the kernel never re-resolves the full path, with a
narrow field mask and automount suppression.

**Lock-free bottom-up roll-up — the single most adaptable technique in this survey.**
Each node carries an atomic `unsearched_children` counter.
When a node finishes, `finishNode` walks toward the root:

```c
while (node != NULL && prev == 1) {
    struct entry *parent = node->parent;
    if (parent != NULL) {
        atomic_fetch_add(&parent->size, node->size);
        atomic_fetch_add(&parent->shared_size, node->shared_size);
        prev = atomic_fetch_sub(&parent->unsearched_children, 1);
    }
    node = parent;
}
```

Whichever thread decrements a parent’s counter from 1 to 0 is the one that continues
upward; every other thread stops.
Roll-ups therefore complete bottom-up **with no barriers, no joins, and no locks** — the
traversal and the aggregation are the same pass.
This is exactly the primitive a multi-metric hierarchical engine needs.

**Batched work distribution.** Children are chained through an intrusive `next` pointer
and pushed onto a lock-free stack with a **single** CAS loop for the whole batch, then
it wakes `min(children, blocked_threads) - 1` workers by semaphore — enough to absorb
the new work, never a thundering herd.
Hot atomics are `alignas(64)` to avoid false sharing.

**Allocate only what will be queried.** A source comment says it plainly: “Process each
entry one at a time, only allocating a struct for dirs or large files.”
Files that cannot make the top-N are rejected against the per-thread heap’s current
minimum *before* any allocation happens.
Directories always get records (the tree needs them); most files never do.

**Field reuse across phases.** `unsearched_children` (traversal) unions with
`num_children` (rendering); the hardlink table pointer unions with the children pointer.
Memory that is dead in one phase is reused in the next.

The one design choice not to copy: `dut` stores each entry’s **full path** in its
flexible array member (parent path + `/` + name), which duplicates every ancestor path
at every depth. ncdu and fsearch store only the name and reconstruct paths by walking
parents. For millions of entries, the parent-pointer approach wins decisively.

`dut` also loses on **cold** cache (pdu and gdu beat it), which its README attributes to
depth-first traversal versus the breadth-first fan-out of the multithreaded frameworks —
DFS has better locality when everything is already in page cache, BFS keeps more
requests in flight when it is not.
That trade-off is worth encoding as a tunable.

### Ncdu 1 and 2: Streaming Architecture and the 25-Byte Record

**ncdu 1.15.1** (`attic/ncdu`, C, MIT) is single-threaded — `readdir()` plus `lstat()` —
but two things stand out.

First, a genuinely good **source/sink separation** documented in `src/dir.h`: inputs
(`dir_scan.c` live scan, `dir_import.c` JSON import) and outputs (`dir_mem.c` build
in-memory tree, `dir_export.c` write JSON) meet at one streaming `item()` callback.
That makes scan→memory, scan→export, import→memory, and import→export all free
combinations. A new engine should adopt exactly this shape, so that the walker and the
snapshot loader are interchangeable sources feeding interchangeable sinks.

Second, a compact record: `struct dir` uses a **flexible array member** for the name
(one allocation for struct + name, not two), intrusive `parent/next/prev/sub/hlnk`
pointers instead of child vectors, a **circular linked list** for hardlink groups with a
`khashl` open-addressing set keyed on `(dev, ino)`, and an **optional** `struct dir_ext`
(mtime/uid/gid/mode) placed in the same allocation only when extended info was
requested. Pay-for-what-you-use field layout, ten years before it was fashionable.

It also `chdir()`s into each directory and stats with relative names — the poor-man’s
version of dirfd-relative traversal — and buffers a whole directory’s names before
recursing, so only one directory stream is open at a time regardless of depth.

**ncdu 2.x** (`attic/ncdu2`, Zig, MIT) is the rewrite, and its author’s published
numbers are the memory targets to beat:

| Entry kind | ncdu 1.16 | ncdu 2.0 |
| --- | --- | --- |
| Regular file | 78 bytes | **25 bytes** |
| Directory | 78 bytes | 56 bytes |
| Hard link | 78 + 8 per dev+ino | 36 + 20 per ino×directory |

A full root-filesystem scan dropped from 429 MB to 162 MB. At 25 bytes per file, 500k
files is ~12 MB and 10M files is ~250 MB — the budget a new engine should hold itself
to.

Reading the current source shows exactly how those numbers are reached, and the
techniques are all portable to Rust.
Records are `extern struct` with `align(1)` on every field, so there is **no padding
anywhere**. The base `Entry` is 24 bytes:

```zig
pub const Entry = extern struct {
    pack: Packed align(1),          // 8 bytes
    size: u64 align(1) = 0,         // 8 bytes
    next: Ref = .{ .ptr = null },   // 8 bytes — next sibling

    pub const Packed = packed struct(u64) {
        etype: EType,               // i3
        isext: bool,                // 1 bit
        blocks: Blocks = 0,         // u60 — "Smaller than a u64 to make room for flags"
    };
```

A `File` is just an `Entry` plus an inline zero-length name array, so 24 bytes + name +
NUL — hence 25 bytes minimum.
`Dir` measures 64 bytes in current source (the published 56 was 2.0-beta1) and `Link`
60\. Three techniques do the work:

- **Steal bits from a wide counter.** `blocks` is a `u60`, freeing 4 bits for the type
  enum and the extension flag inside one `u64`.
- **Intern device IDs.** `DevId` is a `u30` index into a small global device array
  rather than a raw 64-bit `st_dev`, with the comment: “Those are typically 64bits, but
  that’s quite a waste of space when a typical scan won’t cover many unique devices.”
- **Put optional fields *before* the record.** The 19-byte `Ext` (mtime/uid/gid/mode,
  each with its own presence bit) is allocated ahead of the `Entry` in the same block,
  so the canonical pointer still points at `Entry` and `Ext` is reached by stepping
  backward. One allocation holds `[Ext?][Type][name][NUL]`, and entries come from a
  **per-thread arena that is never individually freed**.

Two first-pass claims need correcting.
**ncdu 2 is multithreaded now** — `src/scan.zig` runs a pool with per-thread directory
stacks over a shared 16-slot LIFO queue (threads fully drain their own directory before
consulting it, so contention stays low), with a candid comment that LIFO was chosen
because it was easiest and “it’s impossible for me to predict how that ends up affecting
performance.”
And it deliberately uses **`fstatat`, not `statx`**, for compatibility with
older kernels — a reminder that the newest syscall is not always the right default.

Its hardlink fix for ncdu 1’s O(n²) behavior is a hash map keyed by `(dev, ino)` whose
value is any member of a **circular doubly-linked list** of links sharing that inode,
plus an “uncounted” set of inodes needing stat recomputation that **falls back to full
iteration once it exceeds one eighth of the map** — bounded work either way.

### The Best Snapshot Format Found: ncdu 2’s Binary Export

`src/bin_export.zig` and `src/bin_reader.zig` deserve their own section, because this is
a better fit for metabrowser than the bulk-read design the first pass proposed.

The layout is a signature (`\xbfncduEX1`), then a series of **zstd-compressed data
blocks**, then an **index block at the end** holding one 8-byte `(offset, length)` pair
per block plus the root item’s reference.
Records inside a block are **CBOR maps with small integer keys** (`type`, `name`,
`asize`, `dsize`, `cumasize`, `items`, `sub`, `mtime`, …), so CBOR’s variable-length
integer encoding acts as a varint for free.
Block size adapts from 64 KiB up to 2 MiB as the export grows, to bound the index
block’s size.

Two details are the clever ones:

- **References are `(block_num << 24) | offset`**, and when a reference points *into the
  same block* it is written as a small negative delta instead of the full 64-bit value.
  The comment is blunt about why: “Full references compress like shit and most of the
  references point into the same block.”
- **Opening is O(1).** `open()` reads only the index block at the tail; no data block is
  touched until something asks for it.
  Directory listings are then served by `pread` + decompress into an **8-slot LRU block
  cache**, addressed by item reference.

That is precisely metabrowser’s access pattern: open instantly, then materialize
directories lazily as the user navigates.
A single bulk read of the whole snapshot (the fsearch model) is simpler but forces the
entire tree into memory before the first render.

The format’s own known weakness is documented in a `TODO`: because items are written
depth-first, a parent’s children end up scattered across many blocks, “which will
significantly slow down reading that dir’s listing,” and the suggested fix is to buffer
siblings at the directory level before flushing.
A new engine should simply do that from the start — **write sibling groups
contiguously** so one directory listing costs one block decompression.

The whole design is wired together by a formal **source/sink separation** in
`src/sink.zig` (a tagged union over memory, JSON, and binary sinks) that generalizes
ncdu 1’s `item()` callback.
One consequence is worth stealing: since JSON export cannot be written from multiple
threads, ncdu scans into memory first and replays from there — a clean way to let a
serial sink coexist with a parallel source.

### Bfs and Fd: Syscall-Level Walk Techniques

**bfs** (`attic/bfs`, C, tavianator) is the most syscall-sophisticated walker reviewed,
and its CHANGELOG marks the wins: 3.0 “reads directories asynchronously and in
parallel”; 3.1 “on Linux, bfs now uses io_uring for async I/O … bfs can now perform
stat() calls in parallel.”

- **Raw `getdents64`** with a 64 KiB buffer allocated inline in the directory struct,
  cascading through `posix_getdents`/`getdents64`/raw syscall by platform.
  After a fill, if buffer space remains it issues a *second* `getdents` immediately to
  detect EOF without a later extra syscall.
- **io_uring** for `IORING_OP_OPENAT`, `IORING_OP_CLOSE`, and `IORING_OP_STATX`
  (getdents is explicitly still synchronous — a `TODO` in the source).
  It probes per-opcode availability and falls back per-thread to a synchronous loop, and
  it opts into `SUBMIT_ALL`, `SINGLE_ISSUER`, `DEFER_TASKRUN`, and `ATTACH_WQ` when the
  kernel supports them.
- **Stat avoidance in layers**: `d_type` straight from the dirent; a `bftw_must_stat()`
  predicate; and an *optimizer cost model* that decides whether eager parallel stat
  beats lazy on-demand stat for the given query.
  `statx` uses a minimal field mask, and `AT_STATX_DONT_SYNC` when statting mount points
  to avoid network round-trips.
- **dirfd-relative everything**, with an **LRU cache of open directory fds** sized from
  `RLIMIT_NOFILE`, pinning roots and actively-read directories, and opening relative to
  the nearest open ancestor.
- **Lock-free MPMC queue** using `fetch_add` rather than CAS, cache-line-sized batching,
  exponential backoff then a pool of futex-style monitors.
- **Thread cap of 8** for I/O workers, with the comment that there is “not much speedup
  after 8 threads.”

**fd** (`attic/fd`, Rust) is the contrast: it delegates everything to ripgrep’s `ignore`
crate, adds no platform-specific syscall work, and fetches metadata lazily through a
`OnceCell`. Its gitignore cost is O(1) per entry because `ignore` compiles all patterns
into a single `RegexSet`/`globset` automaton — which is the answer to metabrowser’s
Python-side gitignore hotspot.
fd’s v9 CHANGELOG credits tavianator with 6–13x gains in `ignore` itself.

The gap this opens up is stark.
A naive rayon + `symlink_metadata` walker (dust, and by extension anything built the
obvious way) misses: raw getdents with big buffers, io_uring batching, statx field
masks, `d_type` stat-avoidance, dirfd-relative traversal, fd caching, and lock-free
queue design. That is the difference between mid-pack and leading.

### Three Ways to Persist an Index: Duc, Fsearch, and Gdu

**duc** (`attic/duc`, C, LGPL) stores a KV record **per directory**, keyed by an ASCII
hex `"dev/ino"` string, behind a four-function abstraction (`db_open/close/put/get`)
with six interchangeable backends (Tkrzw, Tokyo, Kyoto, LMDB, SQLite, LevelDB). Each
record holds a header (parent dev/ino, mtime) followed by child entries: 1-byte name
length, raw name, then **SQLite-style varints** for apparent size, actual size, and
recursive count, plus a type enum and — for subdirectories — the child’s dev/ino.
About **22 bytes per child**.

The design lesson is that each child entry stores **pre-computed recursive roll-ups**,
so a query for any directory is a single KV get with no traversal.
Navigating a path costs one get per level.
The anti-lesson: duc has **no incremental logic whatsoever** — the stored directory
mtime is written but never read for staleness decisions, and `duc index` always re-walks
everything.

**fsearch** (`attic/fsearch`, C, GPL) is the Linux answer to Everything, and its record
layout is the most instructive:

```c
typedef struct FsearchDatabaseEntry {
    FsearchDatabaseEntry *parent;           // 8 bytes
    uint32_t attribute_flags;               // 4 bytes
    uint16_t flags;                         // 2 bytes
    alignas(int64_t) uint8_t attributes[];  // packed optional fields
} FsearchDatabaseEntry;
```

Optional attributes (size, mtime, atime, ctime, num_files, num_folders, then the name)
are packed contiguously in the flexible array, with offsets computed from the flags word
— so a run that requests only size and mtime pays only for size and mtime (~33 bytes +
name for a file). **Paths are never stored**: they are reconstructed by walking the
parent chain, so a path like `srv/data/project/src/lib/utils.rs` costs six name strings
across six entries with zero duplication.

Its on-disk format is the best snapshot model found: a `"FSDB"` magic, major/minor
version, and endianness byte; then metadata (index flags, sort flags, entry counts, and
the byte sizes of the folder and file blocks); then the entry blocks with **front-coded
names** — a 2-byte shared-prefix length plus a 2-byte suffix length plus the suffix,
which compresses sorted sibling names like `main.c`/`main.h`/`main.o` down to one
changed byte each — and a `uint32` parent index instead of a pointer.
Loading is a **single bulk `fread` per block** with no random I/O, then a sequential
parse that rebuilds parent pointers from indices.
Saves go to a temp file and `rename()` atomically.
Pre-sorted `uint32` permutation arrays (one per sort order) make switching sort order
instant at 4 bytes per entry per order.

Its watcher is also better than metabrowser’s: **fanotify preferred, inotify as
fallback**, per-folder, with file-handle marks that survive renames, and a
`MONITORED_FAILED` flag when neither works.

**gdu** (`attic/gdu`, Go) is the only *du*-family tool with both multi-metric-per-pass
and persistence. Its `File` struct carries `Mtime`, `Size` (apparent), `Usage`
(allocated), `Mli` (multi-linked inode), and directories add `ItemCount` — all populated
in one walk, with sorting available by five different fields.
It offers three storage backends: BadgerDB (gob-encoded directories, lazily loaded on
demand — the practical one), an ncdu-compatible JSON export, and SQLite.

The SQLite result is an important **negative** finding.
From gdu’s own README on a 90 GB / 400k-file corpus:

| Tool | Cold cache | Warm cache |
| --- | --- | --- |
| diskus | 4.5 s | 271 ms |
| gdu | 4.7 s | 466 ms |
| dust | 6.2 s | 579 ms |
| dua | 6.0 s | 591 ms |
| du | 30.6 s | 645 ms |
| ncdu | 33.2 s | 33.2 s |
| **gdu + SQLite** | **45.4 s** | **8.2 s** |

A general-purpose SQL store costs 10–17x. Whatever the engine persists to, it must not
be a row-per-file relational database on the hot path.
(These are gdu’s numbers on gdu’s corpus, and the corpus differs from dut’s, so the two
benchmark tables above are not directly comparable to each other.)

**dua-cli** (`attic/dua-cli`, Rust, MIT) corrects an assumption from the first pass: it
does **not** use jwalk.
It has a custom work-stealing walker on crossbeam `Injector`/`Stealer` deques with two
job types — `ReadDir` and a `StatCompletion` that **batches 4 entries per stat chunk** —
plus park/unpark idle detection and per-root completion counters.
It carries size (as `u128`, immune to aggregation overflow), mtime, and entry count
simultaneously. Critically, it is the only tool in the survey with a **deliberately
designed library API**: `dua-core` (walk iterators, crossbeam as its only dependency)
and `dua` (tree building and aggregation).
If any existing crate is a candidate to build on rather than replace, `dua-core` is it.

**erdtree** (`attic/erdtree`, Rust) is mostly a lesson in what to avoid: it walks
everything via `ignore`’s `WalkParallel`, collects into a flat `HashMap` of branches,
reassembles a tree afterward, and does all filtering post-traversal.
Its metric is mode-switched like dust’s (`Word`/`Line`/`Byte`/`Block`, one per run).
It does confirm that “walk everything, filter later” is workable, which matters for our
tag-don’t-prune requirement.

### Scc and Tokei: Content Metrics at Scale

These are the state of the art for computing a per-file content metric across a huge
tree — directly relevant to the future words/sentences/paragraphs tier.

**scc** (Go) runs a three-stage channel pipeline: a parallel walker (8 workers) → a
single classifier goroutine → a processing pool of `NumCPU * 4` workers → aggregation.
Channel buffers are deliberately tiny (`NumCPU`) so back-pressure propagates.
It disables GC at startup and re-enables it after 10,000 files.

Its counting loop is a byte-level state machine whose key trick is a **byte-mask
pre-filter**: each language has a `ProcessMask` that is the OR of the first bytes of all
its comment/string/complexity tokens, so most bytes are skipped with a single AND and
compare, branchlessly.

```go
func shouldProcess(currentByte, processBytesMask byte) bool {
    return currentByte&processBytesMask == currentByte
}
```

Tokens are matched through a 256-way branching trie — an O(k) pointer chase with no
hashing. There is no SIMD in the hot loop.

**tokei** (Rust) uses `ignore`’s parallel walker → crossbeam channel →
`rayon::par_bridge`. Its counting is line-oriented over `grep_searcher::LineStep`
(memchr-backed), with an **Aho-Corasick DFA prefilter** to locate the first
“interesting” byte; everything before that point is classified by a *parallel* simple
parse via `rayon::join`, and only the remainder goes through the full state machine.

Both derive their language rules from a `languages.json` at **build time** — scc
generates a Go map literal, tokei renders a Tera template into native Rust `match` arms
— so there is no runtime rule parsing at all.
Detection order in both: exact filename → extension → shebang → heuristic regex guarded
by cheap literal pre-checks.

And the finding that matters most: **neither caches anything across runs**, and
**neither supports per-directory roll-up**. Both aggregate per-language, globally.
The two features metabrowser most needs from a content-metric layer are unbuilt in the
best-in-class tools.

### The Wider Landscape: Instant Answers Over Large Trees

**Windows Everything** does not walk at all: it reads the NTFS Master File Table
directly, then consumes the USN change journal for real-time updates.
Lessons: index once, then apply a change feed; a persisted index makes queries
independent of tree size.
Not portable.

**plocate** is the compression lesson: an inverted **trigram index** with
Zstd-compressed posting lists, which turns a 27-million-file query from mlocate’s ~20 s
linear scan into ~8 ms, in a database ~55–60% smaller (466 MB vs 1.1 GB). It also does
nearly all I/O asynchronously with io_uring. If the engine ever grows name search, this
is the shape.

**Watchman** crawls once, subscribes to OS notifications, and serves queries with a
**clockspec** — “everything changed since clock C.” The `since` model is worth copying
at the API level even though the daemon is too heavy a dependency for a tool installed
via uvx.

**Git’s status machinery** is the closest widely-deployed prior art for the cache tier:
per- file stat fingerprints in the index (with “racily clean” handling for same-second
mtimes); the **untracked cache**, which skips re-listing directories whose mtime is
unchanged; and **fsmonitor** to upgrade the whole thing to notification-driven
invalidation.

**Backup tools** are the best prior art for fingerprint *choice*, and they disagree with
the obvious answer in an instructive way.
Borg defaults to **ctime, size, and inode** — not mtime — precisely because mtime is
user-settable and some applications roll it back after modifying a file, while ctime is
kernel-controlled. Restic requires **both mtime and ctime** (plus inode) to match before
presuming contents unchanged.
Any engine that keys purely on mtime is trusting a value that userspace can forge.

### What Filesystem Watching Can Actually Guarantee (Notify and Watchfiles)

The third pass read the source of the exact watch stack metabrowser runs today:
`watchfiles` (Python, MIT) is a PyO3 wrapper over the Rust `notify` crate (CC0), so
these two codebases define both what the current Python watcher gets and what
`fdu-watch` could do better by using notify directly.

**Backends and recursion.** notify ships six watchers — inotify (Linux), FSEvents
(macOS), kqueue (BSDs), ReadDirectoryChangesW (Windows), a stat-based PollWatcher
fallback, and a null stub.
There is **no fanotify backend** (fsearch’s preferred design would be original work).
Only FSEvents and RDCW are natively recursive; inotify and kqueue emulate recursion by
walking the tree and registering a watch per directory (inotify, bounded by
`max_user_watches`) or per *file* (kqueue, one fd each — a real limit at scale).

**The races are in the source, with no mitigation.** On inotify, when a directory is
created, notify adds a watch for it on receipt of the create event — but files created
inside it between `mkdir` and watch installation produce no events, and notify does
**not** re-list the new directory to catch them.
On kqueue it is worse: a directory-write event triggers a `read_dir` that uses `.find()`
to locate exactly **one** unwatched entry, so multiple files created in a burst are
discovered one per event.
And kqueue has **no overflow signal at all** — dropped events are silent.

**Rename semantics differ per platform, and only one platform is self-contained.**
inotify pairs `From`/`To` with a kernel cookie (and notify synthesizes a `Both` event
carrying both paths) — renames can be applied to a tree atomically with zero filesystem
access. FSEvents emits `RenameMode::Any` with one path and, per a comment in the source,
“no mechanism to associate the old and new sides”; the consumer must stat to learn
whether the path is the vanished source or the new destination.
(watchfiles does perform that stat, mapping the result to added-or-deleted — which is
why renames behave correctly in metabrowser on macOS today: the strategy is sound, and
fdu keeps it, just below the language boundary.)
Windows delivers `From` then `To` sequentially but with no cookie.
PollWatcher cannot see renames at all (Remove + Create).
notify’s own `notify-debouncer-full` crate shows the proven fix: stitch renames by
**file identity** — a `FileId` cache of `(device, inode)` on Unix and volume/file-index
on Windows — when cookies are absent.

**Overflow is signaled — and metabrowser never sees it.** inotify’s `Q_OVERFLOW`,
FSEvents’ `MustScanSubDirs` (kernel- or user-dropped), and RDCW’s buffer-overrun all
surface in notify as an event flagged `Flag::Rescan`, meaning “your view is now
incomplete; re-walk.”
The watchfiles Rust layer maps notify’s rich event model down to a `(change: u8, path)`
set — and in that mapping, an `EventKind::Other` event carrying `Flag::Rescan` falls
through to a branch that **silently discards it**. Rename pairing, cookies,
file-vs-folder kinds, and sub-kinds are flattened away too.
The practical consequence for metabrowser today: after a large burst (a `git checkout`,
an `npm install`), the kernel can drop events, notify duly reports it, and the Python
layer never finds out — the inventory silently diverges until the next full restart.
This is not a bug in metabrowser’s code; it is information watchfiles’ simplified API
cannot carry.

**Batching, for contrast, is done well** and worth keeping: watchfiles polls a shared
dedup set every 50 ms and yields once the set is stable for a step (or a 1.6 s debounce
ceiling forces a flush) — a sound coalescing pattern fdu-watch should reuse, just
without first destroying the event information.

The synthesis for a delta-producing watch layer, per platform:

| Situation | Safe to apply directly? | Required action |
| --- | --- | --- |
| Create/Modify event | path yes, metadata no | statx before emitting `Upsert` |
| Create(Folder) on inotify/kqueue | no | re-list the new directory (watch-setup race) |
| Rename on inotify | yes (cookie-paired) | apply as move, no I/O |
| Rename on FSEvents/Windows/kqueue | no | stitch by file-id, else stat both sides |
| `Flag::Rescan` | no | `InvalidateSubtree` → reconciliation walk |
| kqueue steady-state | no signal on drops | periodic reconciliation sweep |

Every row lands in one of the three delta forms (`Upsert` with fresh stat, `Remove`,
`InvalidateSubtree`), which is the strongest evidence the contract is right: the
platforms’ failure modes are exactly the escalations the API models.
It also settles a question the architecture had left open — **fdu-watch should wrap
notify directly**, not watchfiles, and not raw platform APIs: notify’s backend coverage
and rescan signaling are proven, its losses all occur in the watchfiles layer above it,
and its debouncer-full crate supplies the rename-stitching design (file-id cache) that
the watch layer needs anyway.
CC0/MIT licensing makes both freely adaptable.

### File-Type Recognition Landscape

Four families of prior art:

- **Extension maps:** `mimetypes` (Python), `mime_guess` (Rust), metabrowser’s extension
  sets. Fast, zero I/O, wrong for extensionless or misnamed files.
- **Magic sniffing:** libmagic evaluates a compiled database of offset/type/value tests;
  XDG **shared-mime-info** is the cleaner modern form — declarative rules combining
  weighted globs and prioritized magic tests, plus a `sub-class-of` type hierarchy.
  Rust ports exist (`tree_magic_mini`), as do signature crates (`infer`).
- **Language classification:** GitHub Linguist (and hyperpolyglot) layers strategies in
  cost order: filename → extension → shebang → modeline → content heuristics → Bayesian
  classifier, stopping at the first unambiguous answer.
  scc and tokei both implement essentially this cascade, compiled at build time.
- **Metabrowser’s own manifests:** the `[[kind]]` TOML rules already generalize this
  locally, with priorities and bounded content probes.

The synthesis validates the direction metabrowser has taken: **recognition should be a
priority-ordered cascade of declarative rules, evaluated cheapest-first, with content
tests bounded and optional.** The improvement a Rust engine offers is compiling that
cascade the way scc and tokei do — rules to automata at build time, no runtime rule
parsing — so the same rule files evaluate at walk speed for millions of files.

## Proven Techniques Worth Adapting

The point of reading twelve codebases was to collect techniques that are already proven
in production, rather than inventing them.
Consolidated by layer, with attribution:

**Walk layer**

1. Raw `getdents64` into a large reused per-thread buffer — 64 KiB inline (bfs) or 1 MB
   scratch (dut) — instead of libc `readdir`.
2. Eagerly issue a second `getdents` into leftover buffer space to detect EOF without a
   later syscall (bfs).
3. `openat`-family, dirfd-relative traversal throughout, with
   `O_DIRECTORY|O_NOFOLLOW| O_CLOEXEC` (dut, bfs; ncdu 2 migrated to this from `chdir`).
4. `statx` with a narrow field mask, `AT_SYMLINK_NOFOLLOW`, `AT_NO_AUTOMOUNT`, and
   `AT_STATX_DONT_SYNC` on network mounts (dut, bfs).
5. Use `d_type` from the dirent to skip `stat` entirely when the type is all that is
   needed (bfs); decide eager-vs-lazy stat from a cost model (bfs).
6. LRU cache of open directory fds, sized from `RLIMIT_NOFILE`, pinning roots and
   in-progress directories (bfs).
7. Optional io_uring for `openat`/`close`/`statx` with per-opcode probing and per-thread
   synchronous fallback (bfs).
   Not for getdents — kernel support is still landing.
8. Cap I/O worker threads around 8; measured returns flatten past that (bfs).
9. Batch stat calls in small chunks per work item (dua-core: 4 per job).
10. Push a whole batch of discovered children with a **single** CAS onto an intrusive
    lock-free stack, then wake `min(children, blocked)` workers (dut).
11. Cache-line-align hot atomics; prefer `fetch_add` over CAS loops; exponential backoff
    before parking (dut, bfs).
12. Make traversal order a tunable: DFS for warm-cache locality, BFS fan-out for
    cold-cache queue depth (dut’s README, versus dust/pdu/gdu behavior).

**Roll-up layer**

13. **Atomic `unsearched_children` refcount for barrier-free bottom-up aggregation**
    (dut) — the core primitive, generalized from two `u64`s to a metric vector.
14. Per-thread top-K heaps merged at the end, with early rejection against the heap
    minimum *before* allocating (dut).
15. Store pre-computed recursive roll-ups in each directory record so queries never
    traverse (duc).
16. Carry multiple metrics in one pass rather than mode-switching (gdu; dua-core).
17. Hardlink dedup by countdown-and-remove — decrement remaining link count, drop the
    map entry when exhausted — rather than an ever-growing seen-set (dua-cli), or
    circular linked lists per group (ncdu).

**Memory layout**

18. Parent-pointer tree with name-only storage; reconstruct paths on demand (fsearch,
    ncdu). Explicitly *not* dut’s full-path-per-entry.
19. Optional attributes packed contiguously behind a flags word, offsets computed from
    the flags — pay only for requested fields (fsearch; ncdu’s `dir_ext`/`Ext`). ncdu 2
    places the optional block *before* the record so the canonical pointer never moves.
20. Single allocation for record + variable-length name (ncdu, dut, fsearch), from a
    per-thread arena that is never individually freed (ncdu 2).
21. **Steal bits from a wide counter** rather than adding a flags byte: ncdu 2 packs a
    3-bit type, a presence bit, and a 60-bit block count into one `u64`.
22. **Intern device IDs** into a small global table and store a narrow index, not a raw
    64-bit `st_dev` (ncdu 2).
23. Zero padding: fully packed, byte-aligned records, accepting slightly worse codegen
    for materially better memory (ncdu 2’s explicit trade-off).
24. Reuse fields across lifecycle phases via unions where the phases are disjoint (dut).
25. Chunked arrays rather than one monolithic vector, to avoid realloc pressure during
    live updates (fsearch).
26. Target ncdu 2’s budget: ~25 bytes per regular file, ~56–64 per directory.

**Persistence**

27. Magic + version + endianness header (fsearch, ncdu 2). Pin any enum whose numeric
    value reaches the file format, and say so in the code (ncdu 2’s `EType`).
28. **Compressed blocks plus an index at the tail**, so opening costs one small read and
    data blocks decompress on demand into a small LRU cache (ncdu 2). Prefer this over a
    single bulk read of everything (fsearch) when the consumer navigates lazily.
29. **Item references as `(block << k) | offset`, delta-encoded when intra-block** —
    full references defeat the compressor and most references are local (ncdu 2).
30. Adapt block size upward as the file grows, to bound index size (ncdu 2).
31. Write sibling groups contiguously so one directory listing costs one block
    decompression (ncdu 2’s documented `TODO`, worth doing from the start).
32. Front-coded names against the previous sorted entry (fsearch).
33. `u32` parent indices instead of pointers; rebuild pointers on load (fsearch, ncdu
    2).
34. Varint-encode sizes, counts, and inode numbers — CBOR’s integer encoding gives this
    for free (duc, ncdu 2).
35. Pre-sorted permutation arrays for instant sort-order switching, 4 bytes/entry/order
    (fsearch).
36. Atomic temp-file + `rename()` persistence; treat a corrupt snapshot as empty rather
    than as an error (fsearch, flowmark-rs).
37. Whole-cache fingerprint invalidation from version + config + rule-set hash
    (flowmark-rs).
38. Do **not** put a row-per-file relational store on the hot path (gdu’s SQLite
    backend: 10–17x slower).
39. When a sink is inherently serial but the source is parallel, stage through memory
    and replay rather than serializing the source (ncdu 2’s JSON export).

**Content metrics**

40. Byte-mask pre-filter to skip uninteresting bytes branchlessly (scc).
41. Aho-Corasick prefilter to find the first interesting byte, with a cheap parallel
    pass over the boring prefix (tokei).
42. Compile rule data to code at build time; no runtime rule parsing (scc, tokei).
43. Reuse a per-worker read buffer, discarding it if it grows past a threshold (scc).
44. Detection cascade ordered by cost, stopping at the first unambiguous answer
    (linguist, scc, tokei).

**Watching**

45. Prefer fanotify with file-handle marks (survives renames), fall back to inotify, and
    flag entries where neither worked (fsearch).
    Note notify has no fanotify backend, so this would be original work layered over it.
46. Expose a `since(clock)` delta query rather than only a live event stream (Watchman).
47. Never swallow the rescan signal: inotify `Q_OVERFLOW`, FSEvents `MustScanSubDirs`,
    and Windows buffer overruns all surface as notify’s `Flag::Rescan`, and dropping it
    silently corrupts any index built on events (watchfiles does exactly this — the
    anti-lesson).
48. Stitch renames by kernel cookie where available (inotify) and by a file-id cache of
    `(device, inode)` elsewhere (notify-debouncer-full’s proven design).
49. After a directory-create event on per-directory-watch backends, re-list the new
    directory — files created before the watch was installed produced no events
    (notify’s inotify source shows the race unmitigated).
50. Coalesce with a stability window: batch events, yield when the batch stops growing
    for one step or a debounce ceiling forces a flush (watchfiles' 50 ms step / 1.6 s
    ceiling), and stat once per batch, not per event.

**Fingerprinting**

51. Include ctime and inode, not just mtime and size — mtime is forgeable by userspace
    (borg, restic).

### Licensing Constraints on Adaptation

This matters before any code is written, and the answer differs per tool:

| Tool | License | How we may use it |
| --- | --- | --- |
| ncdu 1 / ncdu 2 | MIT | Permissive; code may be adapted with attribution |
| dua-cli (`dua-core`) | MIT | Permissive; usable as a dependency or adapted |
| bfs | Permissive (0BSD-style) | Adaptable with attribution |
| gdu | Permissive (Apache/MIT-style) | Adaptable with attribution |
| **dut** | **GPL** | **Ideas only — do not copy code** |
| **fsearch** | **GPL** | **Ideas only — do not copy code** |
| **duc** | **LGPL** | **Ideas only for a static Rust build** |

The most valuable single technique (dut’s atomic-refcount roll-up) and the best snapshot
format (fsearch’s front-coded binary layout) both come from GPL sources.
Algorithms and file-format designs are not themselves copyrightable, so a clean
reimplementation from the descriptions in this document is fine — but the implementation
must be written from the described behavior, not transliterated from their source, and
the design doc should say so explicitly.
Verify each license before implementation; the table above is from the checked- out
copies at the commits in `attic/`.

## What Actually Contributes to Performance (Synthesis)

1. **The floor of a cold scan is one directory read per directory plus one stat per
   entry** — but the constant factor varies by 3–7x depending on *how* you make those
   calls. Raw getdents with big buffers, dirfd-relative statx with narrow masks, and
   io_uring batching are what separate dut and bfs from dust and du.
   Language matters less than syscall discipline; metabrowser’s 7k files/s is a
   Python-and-GIL ceiling, but the gap to the leaders is syscall technique as much as it
   is language.
2. **The floor of a warm re-scan is a stat sweep — unless you persist and revalidate.**
   With a snapshot: load (one bulk read of a compact file, milliseconds) + revalidation
   (parallel stat sweep with the dir-mtime shortcut skipping unchanged directories) +
   re-derivation only for changed entries.
   This is git’s model, and flowmark proves the UX at 23 ms warm.
3. **Content work must be opt-in, lazy, and cached by fingerprint.** Every system that
   touches content bounds the read or caches by identity.
4. **A change feed converts re-scans into deltas** — which is exactly metabrowser’s
   server mode.
5. **Nobody in this space has combined these.** Of twelve tools reviewed, exactly one
   (gdu) persists anything, exactly one (gdu) carries multiple metrics per pass, none
   does per-directory type tallies, and none does mtime-based incremental revalidation.
   The combination is genuinely unoccupied ground.

## Key Insights

- **The design splits cleanly across four exemplars.** dut supplies the parallel
  aggregation primitive, ncdu 2 supplies the packed record layout and the seekable
  snapshot format, fsearch supplies the flags-driven optional attributes and front-coded
  names, and flowmark supplies the cache lifecycle and invalidation discipline.
  dust — the original model for this work — supplies mostly a list of things not to do.
- **The single-`u64` node is the deepest limitation to fix.** Dust’s and erdtree’s
  mutually exclusive metric modes exist because a node holds one number.
  Model per-file records as metric vectors and per-directory roll-ups as **monoid-style
  reducers** (sum, max, min, count, histogram, top-k, count-by-key), and every mode
  becomes one walk, incremental updates become “re-merge the ancestors of dirty nodes,”
  and extensibility becomes “register a reducer.”
  gdu proves multi-metric-per-pass costs nothing; dut’s refcount provides the parallel
  mechanism.
- **Incremental revalidation is the unoccupied niche, and it is what metabrowser
  actually needs.** duc writes a directory mtime it never reads.
  gdu persists but never revalidates.
  scc and tokei recompute everything every run.
  The prior art for doing it properly is not in this tool category at all — it is in
  git, borg, and restic.
- **Serve-stale-then-revalidate is the honest way to be “instant.”** Everything,
  Watchman, and git all answer from the index immediately and reconcile asynchronously —
  the same two-phase pattern metabrowser’s UI already has (first-paint depth-2, then
  deepen).
- **Persistence format choice is load-bearing, with a proven wrong answer and a proven
  right one.** gdu’s SQLite backend is 10–17x slower than its in-memory path.
  In the other direction, ncdu 2’s binary export is the strongest design found anywhere
  in the survey: compressed blocks, a tail index, delta-encoded intra-block references,
  and O(1) open with lazy per-directory decompression.
  That last property matters more than decode throughput, because it matches how
  metabrowser and its users actually navigate — open now, expand later.
- **Filesystem events are hints, not truth — and the current stack loses the one signal
  that says so.** Reading notify and watchfiles settled the watch layer’s design: only
  inotify renames are self-contained; every other event needs a stat, a re-list, or a
  file-id match before it can update an index; and the overflow flag that means “your
  view is now incomplete” is silently discarded by watchfiles before Python ever sees
  it. A delta contract with an explicit `InvalidateSubtree` escalation is not a
  nice-to-have — it is the shape the platforms’ failure modes demand.
  This finding also matters to metabrowser today, independent of fdu: after event bursts
  large enough to overflow kernel queues, the Python inventory can silently diverge
  until restart.
- **Metabrowser’s plugin classification dialect is a good seed for the rules format**,
  and scc/tokei show how to make it fast: compile the rules to code at build time.
- **Python is the integration layer, not the hot path.** The measurements now justify
  what the search spec deferred: 70 s cold walks at the cap, ~1.5 s gitignore parsing,
  per-request full-index scans for the recent view.

## Proposed Architecture

### The Shape: Three Artifacts, One Contract

Frollup is organized around three artifacts and the contract that connects them:

1. **The index** — the in-memory hierarchical structure: packed entry records (ncdu
   2-style) plus per-directory reducer state.
2. **The snapshot** — the index serialized (ncdu 2-shaped seekable block format), plus
   an optional append-only journal of deltas since the last snapshot.
3. **The delta** — a typed, clocked description of change: the *only* way the index or
   the cache is ever modified, and the same type consumers receive as a change feed.

Everything else is a **producer** or **consumer** of deltas.
The walker produces deltas (a cold scan is just a large batch of upserts).
The revalidator produces deltas (the diff between snapshot and reality).
The watch layer produces deltas (verified, coalesced filesystem events).
The index consumes deltas and re-rolls reducer state; the journal consumes deltas and
makes the cache durable; metabrowser’s SSE bus consumes deltas and pushes them to
browsers.
This generalizes ncdu’s source/sink separation — which proved that scan→memory,
scan→export, import→memory all fall out free once the streaming interface is right —
from records to *changes*.

A deliberate consequence: **watching is not intrinsically tied to the roll-up logic.**
The index and reducers know nothing about filesystem events — they know `apply(Delta)`,
full stop. A batch CLI run, a test harness feeding synthetic deltas, and a live watcher
are indistinguishable to the roll-up code.
What the design owes the watch use case is not coupling but *cheapness*: `apply` must be
fast enough (O(depth) for the common case, bounded re-merge otherwise) that a stream of
small deltas is a natural fit rather than a retrofit.
Cheap incremental apply is also what makes revalidation sweeps and journal replay fast,
so the watch layer rides on a property the engine wants anyway.

```text
producers                      contract                consumers
─────────                      ────────                ─────────
fdu-scan  (walk, revalidate) ─┐               ┌─ index (in-memory rollups)
fdu-watch (fs events)  ───────┼─→  Delta @clock ──┼─ journal / snapshot (disk cache)
journal replay (on open)  ────────┘               ├─ since(clock) feed (Python, SSE)
                                                  └─ exports (JSON, CLI output)
```

### Crate Split

One Cargo workspace (mirroring flowmark’s feature-gated layout).
The watch layer is a separate crate precisely because the CLI’s one-shot calls never
need it, while the metabrowser server always wants it:

```
fdu-types     records, reducer traits, Delta/Clock, type-rule schema (no I/O)
fdu-index     the in-memory tree; apply(Delta) -> updated rollups + emitted feed
fdu-scan      parallel walker + revalidator (dut/bfs techniques); emits Deltas
fdu-watch     optional: notify-based watcher; raw events -> verified Deltas
fdu-snapshot  seekable snapshot read/write + delta journal (ncdu 2-shaped)
fdu           facade: open/refresh/watch/query wired together
fdu-cli       bin: human tree output à la dust/dut + stable JSON/JSONL
fdu-py        PyO3 cdylib: in-process API for metabrowser; abi3 wheels via maturin
```

`fdu-cli` depends on scan + snapshot + index but not watch.
`fdu-py` includes watch behind a feature so metabrowser gets the full live pipeline
in-process. The sub-library boundaries deliberately track what metabrowser implements in
Python today — `walker.py` → fdu-scan, `inventory.py` → fdu-index, `watch_backends.py` →
fdu-watch — so each can be adopted (or skipped) independently.

### The Delta Contract

A `Delta` is a batch of entry changes stamped with a monotonic `Clock` (Watchman’s
clockspec, made local):

- `Upsert { parent, name, kind, fingerprint, attrs }` — entry appeared or changed;
  carries a *fresh stat*, never just an event.
- `Remove { path }` — entry gone; implies removal of any descendants.
- `InvalidateSubtree { path, reason }` — escalation: the producer cannot describe the
  change precisely (watch overflow, unpaired rename, watch-setup race) and the consumer
  must re-scan that subtree.
  The scan crate turns an `InvalidateSubtree` back into precise deltas, so escalation is
  closed-loop.

Three properties make the contract clean:

- **Deltas carry truth, not hints.** The watch layer stats before it emits (events on
  most platforms carry no metadata — see the watch-layer findings).
  Consumers never interpret raw filesystem events.
- **Deltas are idempotent.** An `Upsert` with an unchanged fingerprint is a no-op.
  This makes journal replay, at-least-once delivery, and overlap between a revalidation
  sweep and live watch events all safe — no coordination needed beyond the clock.
- **Deltas are the serialization unit.** The journal on disk is the same type encoded
  with the snapshot’s CBOR/varint conventions; the Python/SSE feed is the same type
  rendered as JSON. One schema, three uses — which is what keeps the in-memory
  structure, the serialized form, and the update API from drifting apart.

**Incremental roll-up maintenance.** Applying a delta re-merges reducer state up the
ancestor chain. Reducers split into two classes, and the API should make the class
explicit: **invertible** reducers (sums, counts, count-by-type) apply differentially in
O(depth); **non-invertible** reducers (max/min mtime, top-k) can absorb additions in
O(depth) but on removal may need their directory’s state re-merged from its direct
children (O(children) at that level, standard incremental-view-maintenance behavior —
metabrowser’s per-parent newest-mtime *heaps* in `inventory.py` are exactly this
workaround, done by hand for one metric).
Watch-driven churn is small and localized, so this stays cheap; the pathological case
(removing the max in a million-entry directory) is bounded by one directory re-merge.

### The Watch Layer (fdu-watch)

The watch layer’s job is narrow: turn an unreliable platform event stream into the
trustworthy delta stream defined above.
It is strictly additive — removing the crate leaves scan, index, snapshot, CLI, and
Python surfaces fully functional, just without live updates between refreshes.
From the notify/watchfiles source review (see findings), its job means:

- **Build on notify directly**, not watchfiles (whose simplified API destroys rename
  pairing and the rescan flag — see findings) and not raw platform APIs (notify’s six
  backends and overflow signaling are proven).
  fanotify support, which notify lacks, can be layered later per fsearch’s design where
  privileges allow.
- **Debounce and coalesce** raw events per path (keep-latest wins) with a stability
  window, like watchfiles’ 50 ms step / 1.6 s ceiling batching loop — but *without*
  discarding event kind and rename pairing on the way.
- **Verify before emitting**: statx at the end of each batch (once per path, not per
  event), so every coalesced event becomes an `Upsert` with a fresh fingerprint or a
  `Remove`; apply inotify’s cookie-paired renames directly and stitch the rest by
  file-id (notify-debouncer-full’s cache design); re-list any directory whose
  create-event raced its watch registration; and turn `Flag::Rescan` — plus periodic
  sweeps on kqueue, which cannot signal overflow — into `InvalidateSubtree` deltas that
  the scan crate resolves.
- **Select backends the way metabrowser already does** (native for local filesystems,
  polling for NFS/FUSE/CIFS — that tuned policy ports down from `watch_backends.py`),
  and mark entries where watching failed rather than silently not watching (fsearch’s
  `MONITORED_FAILED`).
- **Feed the journal as well as the index**: applied deltas append to the on-disk
  journal (or, minimally, mark dirty subtrees in a persisted dirty-set), so the cache
  stays warm continuously instead of only at shutdown snapshots.

**Compatibility with metabrowser’s proven behavior.** Metabrowser’s watcher works well
in daily use on macOS, and it is worth being precise about *why*, because fdu-watch must
preserve those semantics rather than reinvent them.
The Python layer already treats every event as a hint: file creates and modifies are
answered with a fresh `FsEntry.for_stat()` (a re-stat, never trusting the event),
created directories trigger `inventory.rewalk_subtree()` (a full re-list, which
incidentally papers over the watch-setup race), deletes cascade through the inventory,
and rename ambiguity never surfaces because watchfiles resolves FSEvents’ unpaired
renames by statting (exists → added, gone → deleted) before Python sees them.
In other words, metabrowser converged empirically on exactly the verify-then-emit
strategy this design formalizes — fdu-watch keeps the same event-to-action mapping,
moves it from Python to Rust, and adds the two things the current stack cannot provide:
overflow handling (the dropped `Flag::Rescan`) and deltas that carry verified metadata
instead of bare paths.
Metabrowser is young, so its watcher should be treated as evidence, not specification —
but where fdu-watch’s behavior differs from what demonstrably works on macOS today, the
difference should be deliberate and tested, and the migration path (below) lets the two
run side by side until parity is shown.

Because both the index and the watcher live in Rust, an event that today crosses into
Python, gets statted by Python, and mutates Python dicts never surfaces at all unless a
consumer subscribed to that part of the tree — Python receives coalesced deltas via
`since(clock)` or a callback, not raw events.
Hosts that want to keep their own watcher (metabrowser’s tested NFS fallbacks, say) can
instead push external events into the same pipeline: `index.ingest_events(paths)` treats
them as unverified hints and runs the same verify-then-emit path.

### Cache Coherency: Snapshot + Journal

Three options for keeping the on-disk cache honest while the index changes live:

- **A. Rewrite on quiesce** — snapshot the whole index atomically after a settle period
  and at shutdown. Simple; write cost proportional to tree size; a crash loses only
  warmth, never correctness (the next open revalidates).
  **Phase-1 choice.**
- **B. Snapshot + append-only delta journal** — the WAL pattern: append applied deltas
  (the same serialized type) to a sidecar file; on open, load snapshot, replay journal,
  then revalidate only what the fingerprints say is stale; compact into a fresh snapshot
  when the journal exceeds a threshold.
  Bounded incremental writes, faster warm opens after churny sessions.
  **The growth path — and cheap to reach, because the journal record format is the delta
  type that already exists.**
- **C. Persisted dirty-set only** — on watch events, persist just the set of dirty
  subtree roots; next open revalidates those and trusts the rest.
  Minimal write amplification, weakest warm-open story.
  Useful as a degraded mode when the journal cannot be written (read-only cache dir).

In all three, correctness never depends on the watcher: the revalidation sweep at open
remains the backstop, so a missed event costs staleness-until-next-open at worst — the
same guarantee git’s fsmonitor design provides by layering notifications *over* stat
fingerprints rather than replacing them.

### Data Model

- **File record**, following fsearch: a parent index (`u32`), a flags word, and optional
  attributes packed contiguously behind that flags word — size, allocated blocks, mtime,
  ctime, inode/device, resolved type id, compound extension id — with the name last.
  Names only; paths are reconstructed by walking parents.
  Target ~25–32 bytes per file plus name, matching ncdu 2.
- **Metrics as reducers.** A metric declares id, version, input tier (stat-only vs.
  content), and a commutative merge.
  Built-in stat-tier: total bytes, allocated bytes, file/dir counts, newest/oldest
  mtime, mtime-recency histogram, size histogram, count-and-bytes by file type, top-k
  largest, top-k most recent.
  Content-tier (later): line/word/sentence/paragraph counts per document type.
- **Hierarchical roll-ups** computed during the walk via dut’s atomic child-counter,
  with the counter generalized so that the thread which zeroes a parent merges the full
  reducer vector rather than two `u64`s. Every directory stores its merged state, so
  queries read it directly (duc’s lesson) and incremental updates re-merge only the
  dirty ancestor chain — the same shape as metabrowser’s `_update_ancestor_aggregates`,
  over arbitrary metrics.

### Cache and Revalidation (Three Tiers, Git-Shaped)

1. **Snapshot.** Full inventory + roll-up state, persisted per root under the user cache
   dir keyed by hash of the canonical root (flowmark’s layout), in **ncdu 2’s shape**:
   magic + version header, zstd-compressed data blocks, an index block at the tail,
   records as varint-keyed maps, item references as `(block << k) | offset`
   delta-encoded when intra-block, and sibling groups written contiguously so one
   directory listing costs one block decompression.
   Opening reads only the index; blocks decompress on demand into a small LRU cache.
   Borrow front-coded names and optional pre-sorted permutation arrays from fsearch.
   An **engine fingerprint** (version + config + rule-set hash) invalidates wholesale on
   mismatch. Atomic temp-file + rename; corrupt equals empty.
2. **Revalidation.** On open, a parallel sweep comparing stat fingerprints — **size,
   mtime, ctime, and inode**, per borg/restic, not mtime alone.
   Directories whose own mtime is unchanged skip re-listing (git’s untracked-cache
   trick); files with matching fingerprints keep their derived data (type verdicts,
   content metrics) with zero reads.
   Only changed entries re-derive.
   Results stream as deltas so callers serve the stale snapshot instantly and reconcile.
3. **Watch mode.** In a long-lived process, `fdu-watch` keeps the index and cache
   perpetually warm through the delta pipeline described above, and a Watchman-style
   `since(clock)` query exposes the same deltas to consumers.

Content-derived data caches by `(stat fingerprint, analyzer id, analyzer version)` —
flowmark’s fingerprint invalidation applied per-analyzer rather than whole-cache.

The three tiers are not alternatives but a ladder of freshness: the snapshot answers
instantly, the revalidation sweep guarantees correctness at open, and the watcher keeps
the gap between the two near zero while the process lives.
Correctness never rests on tier 3.

### File-Type Recognition Engine

- Rules as data, in a TOML dialect deliberately compatible with metabrowser’s `[[kind]]`
  manifests, with priorities and a `sub-class-of`-style category hierarchy.
- Compiled cheapest-first the way scc and tokei do it — extension hash maps, glob sets,
  and Aho-Corasick magic tables, generated at build time rather than parsed at runtime —
  with content probes only when cheap tiers are ambiguous and the caller asked for
  content-level confidence.
- Ships a standard rule set; consumers and plugins layer more on top.
  Python-side detectors needing arbitrary logic still run in Python, downstream of the
  engine’s verdict.

### Python Embedding and uv Packaging

- **A. Binary wheel + subprocess** (flowmark-rs’s model, maturin `bindings = "bin"`):
  simplest, total version isolation, JSON/JSONL over stdout.
  Right for CLI and agent use; wrong as metabrowser’s primary path, which wants a
  persistent in-process index.
- **B. PyO3 cdylib** (maturin abi3 wheels): in-process module owning a thread pool and
  watcher, releasing the GIL during native work, exposing `open(root, config) -> Index`,
  `index.query(...)`, `index.since(clock)`, `index.refresh()`, `index.entries(...)`.
  abi3 keeps the wheel matrix to one per OS/arch; uv builds and consumes maturin
  projects natively. **Design the API around bulk operations** — return structured
  results once, not per-item; a million small zero-copy calls lose to one large call.
- **C. Both from one workspace** — the recommendation, mirroring how `walk.py`
  reproduces `/api/tree` today.

Integration seam: the engine replaces the walker + inventory hot path (cold boot walk,
aggregates, recent/tree queries, gitignore evaluation), emitting the record stream
`InventoryIndex` already consumes, while the SSE bus, projections, plugin API, and
classification-dependent views stay untouched.

### Agent Skill Angle

Because warm queries are milliseconds, agents can call the CLI freely: tally a tree by
type, top 20 largest, what changed in the last hour, full JSON inventory of a subtree.
A small skill (like `skills/metabrowser`) would document the CLI with `--help` as source
of truth, giving agents instant tree insight without a server and giving the engine a
second consumer that keeps the CLI honest.

## Comparison Matrix

Grouped by what each tool proves.
“Warm re-run” means a second run over an unchanged tree.

| Tool | Lang | Parallel walk | Syscall level | Metrics/pass | Persists | Revalidates | Library API |
| --- | --- | --- | --- | --- | --- | --- | --- |
| du | C | no | readdir + lstat | 1 | no | no | no |
| ncdu 1 | C | no | readdir + chdir-relative lstat | 1 | JSON export | no | no |
| ncdu 2 | Zig | **yes** (LIFO queue) | openat + fstatat | 1 | JSON + **binary, seekable** | no | no |
| dust | Rust | rayon `par_bridge` | `symlink_metadata` | 1 (mode-switched) | no | no | no |
| dua-cli | Rust | **custom work-stealing** | batched stat (4/job) | 3 | no | no | **yes (2 crates)** |
| pdu | Rust | rayon | std | 1 | no | no | partial |
| diskus | Rust | rayon | std | 1 (total only) | no | no | no |
| gdu | Go | goroutine fan-out | std | **5** | **Badger/SQLite/JSON** | no | informal |
| erdtree | Rust | `ignore` WalkParallel | std | 1 (mode-switched) | no | no | no |
| **dut** | C | custom lock-free pool | **getdents64 + dirfd statx** | 2 | no | no | no |
| **bfs** | C | main + I/O workers | **getdents64 + io_uring + statx masks** | n/a (find) | no | no | no |
| fd | Rust | `ignore` WalkParallel | std, lazy | n/a (find) | no | no | no |
| duc | C | no | readdir + lstat | 3 (recursive) | **KV per directory** | no | yes (libduc) |
| fsearch | C | no (walk) | readdir + fstatat | 2 | **binary index** | no (watcher only) | no |
| scc / tokei | Go / Rust | pipeline / rayon | std | content | no | no | tokei: yes |
| Everything | — | n/a (MFT) | MFT + USN journal | metadata | yes | journal | no |
| Watchman | C++ | yes | notifications | file list | yes | notifications | socket |
| git status | C | partial | stat fingerprints | status | yes (index) | **yes** | libgit2 |
| metabrowser | Python | no (GIL) | `os.scandir` | 3 | no | watcher only | internal |
| **Proposed** | Rust | custom, dut-style | getdents + statx + opt. io_uring | **extensible** | **binary snapshot** | **yes** | **Rust + Py + CLI** |

## Options Considered

### Option A: Wrap an Existing Tool as a Subprocess

**Description:** Shell out to dust/gdu/dut `--json` for roll-ups.

**Pros:** Zero engine code; battle-tested walkers.

**Cons:** No revalidation, so every call is a full rescan — it solves the wrong problem.
Display-shaped JSON, one or two metrics, no type tallies, no library API. gdu is the
only one with persistence and its stored backends are the slow path.
Would still need all the inventory and cache work on top.

### Option B: Adopt Watchman

**Description:** Run Watchman as a sidecar.

**Pros:** Mature clockspec/subscription model, proven at scale.

**Cons:** Heavy operational dependency for a local-first tool installed via uvx;
provides file lists and changes, not roll-ups, tallies, type recognition, or content
metrics.

### Option C: Optimize the Python Path

**Description:** Persist `InventoryIndex`, add multiprocessing, stay in Python.

**Pros:** No new toolchain; incremental delivery in the current codebase.

**Cons:** The GIL caps stat-sweep parallelism and multiprocessing adds serialization
overhead comparable to the work saved.
None of the syscall-level techniques that produce the 3–7x gaps (getdents buffers,
dirfd-relative statx, io_uring) are reachable from Python.
Ceiling is maybe 2–3x, and none of it is reusable outside metabrowser.

### Option D: Build on `dua-core`

**Description:** Take dua-cli’s MIT-licensed work-stealing walk crate as the traversal
layer and build reducers, snapshot, and type rules on top.

**Pros:** Skips the hardest concurrency code with a proven, minimal-dependency
implementation; MIT license is clean; batched stat jobs are already there.

**Cons:** Its stat path is `std`-based, so the getdents/statx/io_uring wins need adding
anyway; its record model would need replacing wholesale.
Realistically this is a **phase-1 accelerator** — start here to get correct behavior
fast, replace the syscall layer once benchmarks justify it.

### Option E: Ground-Up Rust Engine (Recommended)

**Description:** The workspace described above, assembling the proven techniques
catalogued in this document.

**Pros:** Removes every measured hot path at once; warm-start server boots and instant
agent queries; materially lifts the 500k cap.
Reusable as library, CLI, skill, and Python module.
Every major subsystem has a working exemplar to copy rather than invent.

**Cons:** A new codebase and CI matrix (Rust toolchain, wheel builds) to own.
Rule-dialect compatibility with plugin manifests needs care.
A native wheel raises the supply-chain review bar (mitigated by being first-party, like
flowmark-rs). Two of the best exemplars are GPL, so those parts must be clean
reimplementations.

## Recommendations

1. **Build Option E as a standalone repo** named **fdu** (see *Naming* below),
   optionally bootstrapping traversal from `dua-core` (Option D) to reach correct
   behavior sooner. Phase 1 is types + index + scan + snapshot + CLI: parallel
   gitignore-*tagging* walk, stat-tier reducers, snapshot + revalidation, dust/dut-style
   tree output plus stable JSON. `fdu-watch` is a later phase — but the `Delta`/`apply`
   contract it needs is phase-1 work, since scan and revalidation already speak it.
   Keep watching decoupled from roll-up logic throughout: the index never learns about
   filesystem events, and the watch crate stays deletable.
2. **Benchmark against dut and gdu, not dust.** Targets: cold-scan within ~1.5x of dut
   on the same corpus; warm re-run (snapshot + revalidation) well under 1 s for 500k
   entries, against flowmark’s 23 ms bar at ~1k files.
   Build the corpus generator first, mirroring flowmark’s
   `benchmarks/generate_corpus.sh`, and always report cold and warm separately — every
   benchmark in this document that omitted that distinction was misleading.
3. **Adopt the memory and snapshot targets explicitly:** ~25–32 bytes per file record
   and O(1) snapshot open with lazy per-directory decompression (both ncdu 2), and no
   relational store on the hot path (gdu’s SQLite result).
4. **Use size + mtime + ctime + inode as the fingerprint**, per borg and restic, not
   mtime alone.
5. **Define the type-rule dialect early** as a compatible superset of the plugin
   `[[kind]]` predicates, compiled at build time, so plugins never need two rule
   languages.
6. **Design queries around `since(clock)` deltas** from day one; cheap now, and it
   unlocks watch-mode and SSE integration later.
7. **Defer content-tier metrics** until the stat tier is solid, but reserve their place
   in the reducer registry and the per-analyzer fingerprint cache now, since that shapes
   the snapshot format.
8. **Record the GPL constraint in the implementation plan** so the dut- and
   fsearch-derived designs are written from specification, not transliterated.

### Naming

The engine is named **fdu** — `fd` + `du`, read as “fast du.”
It follows the naming tradition of the tools it learns from (`fd`, `rg`, `du`), is three
keystrokes, and needs no explanation at a shell prompt.

Availability was verified against the registries that matter, calibrated against
known-present and known-absent names so the signals could be trusted:

| Registry | Check | Result |
| --- | --- | --- |
| PyPI | Simple index (PEP 503) and JSON API | free |
| crates.io | API and sparse index (what cargo reads) | free |
| crates.io | similarity blockers `f-du`, `f_du`, `fd-u`, `fd_u`, `FDU` | all free |
| Homebrew | formula API | free |

So the crate, the PyPI distribution, the binary, and a future Homebrew formula can all
be `fdu`, with sub-crates as `fdu-types`, `fdu-index`, `fdu-scan`, `fdu-watch`,
`fdu-snapshot`, `fdu-cli`, and `fdu-py`.

Two prior uses of the name exist, neither blocking and both worth knowing: an npm
package `fdu` ("inspect disk usage with flame graph," last published 2022) and a dormant
GitHub script `nicollet/fdu` (a `.SIZE`-file du cache).
Neither is on PyPI, crates.io, or Homebrew.
Re-verify immediately before first publish, since availability is a race.

A methodological caution for whoever re-checks: `https://pypi.org/project/<name>/` can
return HTTP 200 with an anti-bot interstitial (`<title>Client Challenge</title>`) for
names that do not exist.
Use the Simple index or the JSON API, and calibrate against a known package, or the
check will report false positives.

## Open Questions

Two questions from the first pass are now **resolved**:

- ~~Can the `ignore` crate walk everything and tag ignored rather than pruning?~~
  **Yes.** `ignore::gitignore::GitignoreBuilder`/`Gitignore` can be used standalone —
  build the matcher from `.gitignore` files and call `matched_path_or_any_parents()` on
  each path during a normal walk.
  Pruning is a `WalkBuilder` behavior, not a matcher limitation.
  erdtree confirms the walk-everything-filter-later pattern in practice.
- ~~Which snapshot serialization format?~~ **A seekable, block-compressed binary format
  modeled on ncdu 2’s**, not a single flat serde/rkyv blob.
  Reading ncdu 2’s implementation changed this answer: what matters for metabrowser is
  not raw deserialize throughput but that opening is O(1) and directory listings
  materialize lazily, which a compressed-blocks
  + tail-index + LRU design gives and a monolithic decode does not.
    Zero-copy framing (rkyv-style) remains attractive *within* a block; that is now a
    narrower, deferrable choice.
    Format-version fingerprinting keeps evolution cheap either way.

Still open:

1. How much of classification belongs engine-side?
   Proposal: the engine yields type/category verdicts from compiled rules; adapter-level
   sniffing (which agent wrote a JSONL) stays in Python plugins.
   Validate against real plugin manifests.
2. Hardlink attribution policy.
   dust uses an order-dependent global seen-set; dua counts down remaining links; gdu
   divides size among linked items; dut tracks shared-vs-unique in two columns.
   For *stable, cacheable* roll-ups the engine needs a deterministic rule — dut’s
   shared/unique split is the most informative, but it must survive incremental updates,
   which none of these tools attempt.
3. Watcher ownership in metabrowser: the delta contract supports both — `fdu-watch`
   replacing `watch_backends.py` outright (the clean end state: watchfiles wraps the
   same notify crate anyway, and events then never cross into Python), or metabrowser
   keeping its watcher and pushing paths through `ingest_events()` as unverified hints
   (the low-risk migration step that preserves its tuned NFS/FUSE fallbacks).
   The open part is sequencing: which ships first, and what the acceptance test for
   dropping the Python watcher looks like.
4. Where do bounded content probes cap out for type recognition (first 8 KiB?), and is
   sniffing on-demand-only at first so the walk stays stat-pure?
5. Is io_uring worth phase-1 complexity, or a phase-3 accelerator behind a feature flag?
   bfs’s per-opcode probing plus synchronous fallback is the proven pattern, but it is a
   large amount of machinery for a Linux-only win.
6. Does the DFS/BFS traversal-order trade-off warrant a runtime switch, and can
   warm/cold state be detected rather than configured?
7. What is the revalidation cost curve in practice?
   The whole design rests on “a parallel stat sweep of 500k unchanged files is fast
   enough to feel instant,” and that number should be measured before the format is
   frozen.
8. Journal compaction policy: when the delta journal outgrows its threshold, compact
   synchronously at quiesce or in a background thread?
   And should `since(clock)` be servable across a process restart from the journal (nice
   for SSE resume) or only within one process lifetime (simpler)?
9. Non-invertible reducer cost under churn: the bounded re-merge on removal is fine in
   theory; measure it on a pathological case (repeated deletes of the current max in a
   100k-entry directory) before committing to which built-in metrics are
   watch-maintained versus revalidation-only.

## Next Steps

- Review this document; decide go/no-go on Option E, the standalone-repo question, and
  whether to bootstrap from `dua-core`.
- If go: draft a plan spec for phase 1 (core + CLI + benchmarks), with beads for the
  walker, reducers, snapshot store, revalidator, type-rule compiler, and benchmark
  harness.
- Prototype the risk spikes first, in this order: (a) revalidation sweep cost at 500k
  entries — the load-bearing assumption; (b) snapshot load time for candidate formats;
  (c) the generalized atomic-refcount roll-up over a metric vector; (d)
  walk-everything-tag- ignored on top of `ignore`’s matcher API.

## References

Source reviewed under `attic/` (commit as checked out):

- [dust](https://github.com/bootandy/dust) v1.2.4 ·
  [flowmark-rs](https://github.com/jlevy/flowmark-rs) v0.3.2 (see its `docs/cache.md`)
- [ncdu 1.15.1](https://github.com/rofl0r/ncdu) (C) ·
  [ncdu 2.x](https://code.blicky.net/yorhel/ncdu) (Zig) ·
  [Ncdu 2: Less hungry and more Ziggy](https://dev.yorhel.nl/doc/ncdu2)
- [dut](https://codeberg.org/201984/dut) · [duc](https://github.com/zevv/duc) ·
  [fsearch](https://github.com/cboxdoerfer/fsearch)
- [bfs](https://github.com/tavianator/bfs) · [fd](https://github.com/sharkdp/fd)
- [gdu](https://github.com/dundee/gdu) · [dua-cli](https://github.com/Byron/dua-cli) ·
  [erdtree](https://github.com/solidiquis/erdtree)
- [scc](https://github.com/boyter/scc) · [tokei](https://github.com/XAMPPRocky/tokei)
- [notify](https://github.com/notify-rs/notify) ·
  [watchfiles](https://github.com/samuelcolvin/watchfiles) (metabrowser’s current
  watcher stack)

Not checked out, consulted via documentation:

- [diskus](https://github.com/sharkdp/diskus) ·
  [pdu](https://github.com/KSXGitHub/parallel-disk-usage) ·
  [ncdu upstream](https://dev.yorhel.nl/ncdu)
- [Everything](https://www.voidtools.com/faq/) ·
  [Watchman](https://facebook.github.io/watchman/) ·
  [plocate](https://plocate.sesse.net/)
- [git untracked cache](https://git-scm.com/docs/git-update-index#_untracked_cache) ·
  [git fsmonitor](https://git-scm.com/docs/git-fsmonitor--daemon) ·
  [borg performance notes](https://borgbackup.readthedocs.io/) ·
  [restic backup docs](https://restic.readthedocs.io/en/stable/040_backup.html)
- [ripgrep `ignore` crate](https://docs.rs/ignore) · [jwalk](https://docs.rs/jwalk) ·
  [rkyv](https://github.com/rkyv/rkyv) ·
  [Rust serialization benchmarks](https://github.com/djkoloski/rust_serialization_benchmark)
- [shared-mime-info](https://specifications.freedesktop.org/shared-mime-info-spec/latest/)
  · [GitHub Linguist](https://github.com/github-linguist/linguist) ·
  [hyperpolyglot](https://github.com/monkslc/hyperpolyglot) ·
  [infer](https://docs.rs/infer) · [tree_magic_mini](https://docs.rs/tree_magic_mini)
- [PyO3](https://pyo3.rs/) · [maturin](https://www.maturin.rs/) ·
  [io_uring getdents discussion](https://lwn.net/Articles/843865/)

Metabrowser internals: `src/metabrowser/walker.py`, `inventory.py`, `tree.py`,
`watch_backends.py`, `file_kinds.py`, `plugin_loader/classify.py`, and
`docs/project/specs/active/plan-2026-07-17-scalable-file-search.md`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
