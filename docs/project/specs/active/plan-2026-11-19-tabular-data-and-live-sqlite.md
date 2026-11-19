# Feature: Tabular Data Browsing and Live SQLite

**Date:** 2026-11-19

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft. A design for review: the items under [Key Decisions](#key-decisions)
carry recommendations and are open until the owner approves them.
Nothing here is built.
Epic `mb-lra6` tracks the work; `mb-nv9k` is the owner’s review of the decisions.

## Overview

Metabrowser shows a CSV file as text, a list of YAML records as a tree, and a SQLite
database as an opaque binary file.
All three are tables, and a reader wants the same thing from each: see the columns, sort
and filter the rows, open one record, and follow a reference to the record it names.

This plan adds one generic **table** plugin that owns that experience, and makes it the
UI layer for a set of **source** plugins that depend on it:

- **Delimited text:** `.csv` and `.tsv` files.
- **Record lists:** a JSON or YAML file whose top level is a list of mappings, typed by
  its SoftSchema contract when it has one.
- **SQLite:** any SQLite database, including one another application is writing at that
  moment, read without changing it in any way, with its writes shown as they land.

The table plugin knows nothing about any source.
A source answers a small set of questions (what tables exist, what their fields are,
which rows match a query, what one record holds), and every source is drawn, queried,
tested, and reached from `metab` the same way.

The look follows the knowledge-base browser in
[paraverse](https://github.com/jlevy/paraverse) (`db/src/paraverse_graph/web/`), which
already presents typed records over a graph database through a source-neutral JSON
contract. The approach for reading live databases follows the SQLite research in
[fsqlite](https://github.com/jlevy/fsqlite) and measurements made for this plan
([Reading Another Application’s Database](#reading-another-applications-database)).

## Goals

- **One table experience** for every tabular source: typed columns, server-side sort,
  typed filters and search, keyset paging over arbitrarily large tables, a record view,
  and references drawn as links with hover cards.
- **Clean presentation of all the data.** Every value is visible: nulls are distinct
  from empty strings, a value whose stored type differs from its column’s declared type
  says so, long text and blobs are previewed in the table and shown whole in the record.
- **Strictly nondestructive SQLite.** Opening a database never writes to it, never
  creates or removes a file beside it, never rolls back another process’s journal, and
  never holds a read open long enough to slow its owner.
- **Live.** An open table refreshes when its file changes, including a database whose
  owner is writing through a write-ahead log, while keeping the reader’s scroll
  position, focused row, and unsent filter text.
- **Reusable by construction.** A source plugin declares that it requires the table
  plugin, registers a source, and is done; downstream plugins can add sources the same
  way.
- **CLI parity.** Every route is reachable through `metab --api` and pinned by goldens,
  and the table’s browser state machine runs browserlessly, as
  [AGENTS.md](../../../../AGENTS.md#cli-and-functional-ui-parity) requires.
- **Level up the framework where this needs it**: declared plugin dependencies, plugin
  kinds for binary formats, and live reload for any open file.
  The server, shell, and built-in plugins ship together, so each framework change lands
  with every consumer updated in the same change, with no compatibility layer.

## Non-Goals

- **Editing.** Every source is read-only.
  Writing rows belongs with the trusted editing plan, not here.
- **Arbitrary SQL.** A read-only query console is
  [Decision 7](#decision-7-a-read-only-query-console), deferred.
- **Other database engines.** DuckDB, LMDB, and Parquet follow the same source recipe
  later, each as its own plugin when a consumer appears.
- **A directory of record files as one table** (a folder of SoftSchema records sharing
  one contract, as a knowledge base is laid out).
  The source protocol admits it; it is [an open question](#open-questions).
- **Graph views** of references.
  The record view lists references and back-references; a graph drawing is later work.
- **Network-filesystem guarantees.** SQLite’s own locking is unreliable on network
  mounts, and this plan does not try to fix that; it reports the states it can detect
  ([Decision 8](#decision-8-network-mounts-and-sync-folders)).

## Background

### What Exists Today

- **No table view.** `.csv` and `.tsv` are plain text (`BROWSER_TEXT_EXTS` in
  `src/metabrowser/file_extensions.py`). The structured plugin draws JSON and YAML as a
  virtualized tree, so a list of records reads as a long outline.
  The only shared table styling is the `.data-table` CSS in `static/styles.css`; there
  is no shared table component, and windowing is implemented separately by the
  structured tree, the Pulls panel, the ref selector, and the diff summary.
- **A plugin cannot claim a binary file.** `api_file` classifies directories, JSONL,
  images, and text, and sends everything else to `binary`; plugin `[[kind]]` rules see
  only text and JSONL ([Plugin System](../../architecture/arch-plugin-system.md)).
  Content sniffing (`content_sniff.py`) decides only text versus binary.
- **Plugins share helpers informally.** A built-in publishes `mb.builtins.<name>` and a
  consumer reads it only at render time, after awaiting the provider kind’s assets
  ([Render-Time-Only Namespace Rule](../../../plugins.md#render-time-only-namespace-rule)).
  Nothing declares the dependency, so nothing checks it.
- **An open file does not refresh.**
  [Live Updates](../../../browsing-files.md#live-updates) says an open file shows new
  content on reopen or reload; only files under `.logs` and `.state` with a few
  extensions auto-reload.
  A plugin can subscribe with `mb.onInventoryChange`, but the event stream carries
  entries only to depth two and catalog deltas only for unignored files, and databases
  are usually ignored.
- **SQLite is already read safely in one place.** The GitHub plugin’s pull request
  catalog (`builtin_plugins/github/pull_catalog.py`) checks the 100-byte header, opens
  `mode=ro`, sets `trusted_schema=OFF` and `query_only`, bounds work with a progress
  handler, and classifies damaged versus transient errors.
  It refuses write-ahead-log databases and its helpers are private to its catalog.
- **A specialized reader was removed once.** An LMDB plugin shipped in the first
  standalone commit and was removed the same day, on the rule that specialized binary
  readers and their native dependencies stay out of the core wheel.
  SQLite does not conflict with that rule: Python’s `sqlite3` is in the standard library
  and the repository already depends on it.
- **The object data model draft**
  ([Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md))
  proposes a collection envelope (`rows`, `next_after`, `complete`, `truncated`,
  `generation`) and a shared list host with windowing and an arrival rule.
  This plan adopts the envelope spelling and the arrival rule so the two converge.

### Prior Art: The Paraverse Browser

Paraverse’s browser renders every kind of record in a knowledge base from the base’s own
JSON Schemas. What makes it good, and what this plan keeps:

- **One field descriptor drives everything.** `schemas.py` normalizes JSON Schema into
  `{name, title, type, list, required, ref_kinds, enum, format}`, and that one
  descriptor decides columns, sortability, filterability, formatting, and the record
  layout.
- **The UI sees only a neutral JSON contract**: meta (kinds and counts), schema per
  kind, paged rows of cells, one record, a hover card, and search.
  Its server builds Cypher inside its route handlers; here that layer becomes a source
  protocol so several engines can sit behind one contract.
- **Cells are envelopes resolved on the server**, one batch per page: a scalar, a list,
  `{refs: [...]}`, or `{nested, count, preview}`, so the client never looks up a
  reference by itself.
- **Presentation details:** sticky headers; cells clamped to two lines with a full-text
  tooltip; numbers right-aligned only when the whole column is numeric; enum and boolean
  values that filter the table when clicked; “+N” that opens the related rows as a
  filtered table; removable filter chips; columns that fit the width by hiding default
  columns from the right with a note saying how many; a pinned first column when the
  reader’s chosen columns overflow; hover cards with a grace period; all view state in
  the URL; scroll and focused row restored on Back.
- **Live reload as data motion:** a load stamp, a server-sent `hello`, a coalesced
  reload that repairs the URL when a column disappears, and one amber flash that means
  “the data changed,” distinct from interface motion.

What stays out: its conference-specific kind groups, default columns and card fields,
its typed-ID prefix maps, and any per-dataset logic.
Two choices change for databases: paraverse renders null as blank, but in a database
null and the empty string differ and must look different; and paraverse renders every
row of a page with offset paging, which does not scale to a million-row table.

### Reading Another Application’s Database

A viewer pointed at a browser’s history database or an application’s state database is a
guest. These facts set the access rules; the measurements were made for this plan with
Python’s `sqlite3` on SQLite 3.53.1, the library the repository’s Python environment
loads, as an unprivileged user:

| Situation | `mode=ro` | `immutable=1` |
| --- | --- | --- |
| Write-ahead-log database, owner not running (no `-wal` or `-shm`), writable folder | Reads, but **creates `-wal` and `-shm` and leaves them after close** | Reads; creates nothing |
| Same, read-only folder | Fails: `SQLITE_READONLY_DIRECTORY` | Reads |
| Write-ahead-log database, owner running | Reads committed data, including commits not yet checkpointed into the main file | Would miss uncheckpointed commits: unsafe |
| Rollback-journal database with a hot `-journal` from an interrupted write | Refuses: `SQLITE_READONLY_ROLLBACK`; nothing changes | **Reads the half-written state**: unsafe |

Two more measurements:

- **A held read starves the owner’s checkpoint.** With a reader inside one read
  transaction, the owner’s `wal_checkpoint(TRUNCATE)` reported busy and the log grew
  past a megabyte after a few hundred writes; once the reader’s transaction ended, the
  same checkpoint truncated the log to zero bytes.
- **A commit in write-ahead-log mode leaves the main file untouched.** Only `-wal`
  changed, so a change detector that stats only the database file misses every commit
  until a checkpoint.

The fsqlite research
([portable concurrent SQLite](https://github.com/jlevy/fsqlite/blob/main/docs/research/research-2026-06-06-portable-concurrent-sqlite.md))
adds what holds beyond one host: a shared-memory wal-index cannot work across a network
filesystem, POSIX locks there are unreliable, a sync folder copies a database mid-write
and ignores its sidecars, and a consistent copy of a live database comes only from the
backup API, `VACUUM INTO`, or `sqlite3_rsync`, never from copying the file.
It also names one format worth recognizing: an fsqlite store is a directory holding
`fsqlite.json`, whose `current` file names an immutable snapshot under `snapshots/`;
each snapshot carries `application_id` `FSQL` and two reserved tables, `fsqlite_meta`
and `applied_tx`.

## Design

### Approach

Three layers, each replaceable without touching the others:

1. **The table plugin** (`builtin_plugins/table/`): the browser component, the query
   model, the wire contract, the routes, and the Python source protocol.
   It has no kind of its own.
2. **Source plugins** (`delimited`, `records`, `sqlite`), each declaring
   `requires = ["table"]`, each claiming its kinds and registering one source adapter.
3. **Framework improvements** in core that the layers need and that every plugin gains:
   declared dependencies, binary kinds by magic number, and live reload for open files.

```
 browser                         server
 ┌───────────────────────┐       ┌──────────────────────────────────────────┐
 │ table view (table/)    │ HTTP  │ /api/plugin/table/{tables,schema,rows,   │
 │  list · grid · record  │──────▶│                     record,card}         │
 │  query state in URL    │       │   └─ source registry: kind → adapter     │
 │                        │  SSE  │        ├─ delimited  (csv, tsv)          │
 │ live: mb.watchFile ◀───┼───────│ /api/watch   ├─ records (json, yaml)     │
 └───────────────────────┘       │        └─ sqlite (sqlite_access.py)       │
                                 └──────────────────────────────────────────┘
```

### The Source Protocol

A source adapter is a Python object the table routes call with a resolved, bounded
handle on one file. It answers:

| Method | Returns |
| --- | --- |
| `tables()` | Each table: `id`, `label`, `group` (`tables`, `views`, `internal`), `count` (exact or a lower bound), and whether it has a stable row key |
| `schema(table)` | Field descriptors, the key fields, the default columns, outgoing references, and incoming references (other tables’ fields that point here) |
| `rows(table, query)` | One page in the collection envelope |
| `record(table, key)` | Every field’s full value (bounded per value), with references resolved |
| `card(table, key)` | A short summary for a hover card: label, a few fields |
| `generation()` | An opaque token that changes whenever the source’s content may have changed |

The protocol lives in the table plugin’s Python package
(`metabrowser.builtin_plugins.table.source`) and is re-exported from
`metabrowser.plugin_api`, so an installed plugin can implement it without importing a
private module.
Adapters are synchronous and run on the route threadpool, as sidekicks do
today.

**Field descriptor.** One shape, adapted from paraverse’s:
`{name, title, type, declared_type, nullable, key, list, enum, format, ref, sortable, filterable, numeric}`.
`type` is one of `text`, `integer`, `real`, `boolean`, `date`, `datetime`, `json`,
`blob`, or `unknown`. `ref` is `{table, field}` for a reference.
A source fills in what it knows and leaves the rest null; the client derives nothing a
source could have stated.

**Cell encoding.** A cell is a scalar, or an envelope when a scalar would hide
something:

- `null` is JSON null, drawn as a muted `null`; the empty string is drawn as empty.
- `{text, length}` for text longer than the preview, cut on the server.
- `{blob, length, hex}` for bytes: their size and a short hex preview.
- `{json, preview}` for a JSON value in a text column the schema calls `json`.
- `{ref: {table, key, label}}` for a reference, resolved for the whole page in one
  batched read.
- `{value, stored}` when a value’s stored type differs from the declared type (SQLite’s
  dynamic typing: text in an `INTEGER` column), so the table shows it rather than
  coercing it.

**Query.** One wire shape for every source: `sort`, `order`, `q` (search), typed filters
`f.<field>=<op>:<value>` (`eq`, `ne`, `lt`, `le`, `gt`, `ge`, `null`, `notnull`,
`contains`), `ref=<table>:<key>` (rows that reference one record), `cols`, `after`, and
`limit`. Sort is one field plus the row key as a tie-breaker, so paging is stable.
Search matches text fields only and says which fields it searched.

**Envelope.** The collection convention from the object model draft:
`{rows, next_after, complete, truncated, generation}` plus `columns`, `count`, and
`count_complete`. `after` is an opaque cursor the source minted.
A count a source could not finish within its budget is a lower bound, drawn as “at least
1,000,000”.

**Bounds.** Every route is bounded by named constants defined beside their code and
listed in [Rendering Large Content](../../../large-content-rendering.md): rows per page,
characters per cell preview, bytes per record value, references resolved per page, and a
work budget per request (SQLite opcodes through a progress handler, bytes for text
sources). Each value is set from a measurement recorded beside the constant, per the
repository’s
[measure-before-bounding rule](../../../../AGENTS.md#browser-and-plugin-boundary).

### Routes and the CLI

The table plugin owns one route set, and every source answers through it:

| Route | Serves |
| --- | --- |
| `GET /api/plugin/table/tables?path=` | The source’s tables with counts and groups |
| `GET /api/plugin/table/schema?path=&table=` | Field descriptors, keys, references, defaults |
| `GET /api/plugin/table/rows?path=&table=&…query` | One page in the collection envelope |
| `GET /api/plugin/table/record?path=&table=&key=` | One record in full, with back-references counted |
| `GET /api/plugin/table/card?path=&table=&key=` | A hover card |

The kind of the file at `path` selects the adapter, so a new source adds no route.
Each source has its own goldens through these routes, and `metab --show` goldens pin the
new kinds.
Because every surface is a route, `metab --api` reaches it by construction and
no new CLI mode is needed.

### Framework Improvements

**Declared plugin dependencies.** `[plugin] requires = ["table"]` in a manifest.
The loader refuses a missing or cyclic dependency, loads a provider’s assets before its
dependents’, and `metab --doctor` reports the graph.
In the browser, `await mb.plugins.load("table")` returns the provider’s exports after
its assets have run, replacing the render-time-only `mb.builtins` convention.
Markdown, structured data, agent logs, the folder README panel, and the pull request
page move to it in the same change, and the rule and its test change with them.

**Binary kinds by magic number.** A `[[kind]]` match may name `magic` (an offset and the
bytes expected there) with `exts` as a cheap pre-filter.
`api_file` checks magic rules after images and before the binary fallback, reading only
the sniff prefix it already reads.
The SQLite kind matches `SQLite format 3\0` at offset 0 with extensions `.sqlite`,
`.sqlite3`, `.db`, `.db3`, and `.s3db`; a `.db` file that is not SQLite stays binary.
This also lets a future installed plugin claim LMDB or Parquet without a core change.
The file-type registry gains the missing SQLite extensions with a revision bump.

**Live reload for any open file.** `GET /api/watch?path=&with=` is a server-sent event
stream that stats the file and the named sidecars on a bounded interval and sends
`changed` with the new generation when any of them change, coalescing bursts.
It works for ignored files and deep paths, which the inventory stream does not cover,
and on mounts without filesystem events.
`mb.watchFile(path, {with, onChange})` wraps it and returns a disposer; the shell holds
one connection per open view.
Every open file view gains a reload on change, so the
[Live Updates](../../../browsing-files.md#live-updates) rule that an open file refreshes
only on reopen goes away.

### The SQLite Source

**Shared access helper.** `src/metabrowser/sqlite_access.py` holds the one way the
product opens a database it does not own: header admission, the access choice below,
connection settings, the work budget, and error classification.
The GitHub catalog moves onto it in the same change.

**Choosing how to open**, from a 100-byte header read and a stat of the sidecars, before
SQLite touches anything:

| Header and sidecars | Open | Why |
| --- | --- | --- |
| Rollback journal, no `-journal` | `mode=ro` | Takes a shared lock for the read; creates nothing |
| Any `-journal` present | `mode=ro`; on `SQLITE_READONLY_ROLLBACK`, the state **writer busy or interrupted** | Never read a half-written file; never roll back another process’s journal |
| Write-ahead log, `-wal` and `-shm` present | `mode=ro` | The owner is live; reading through its wal-index is the normal reader protocol and creates nothing |
| Write-ahead log, no sidecars, or a read-only folder | `immutable=1`, validated | `mode=ro` would create sidecars or fail; the read is valid only if the file’s identity, size, and modification time match before and after and no sidecar appeared, else it is retried once and then reported as changing |
| Immutable content: a Git revision, an fsqlite snapshot | `immutable=1`, or deserialized into memory for a Git blob under a size cap | The bytes cannot change |

**Every request is short.** Each route call opens a fresh connection, reads inside one
short transaction, and closes it; no connection or transaction outlives a request, so a
reader never pins the owner’s log.
Keyset paging (by the sort value and the row key) makes each page an index seek rather
than an offset scan.
Connections set `query_only`, `trusted_schema=OFF`, a small cache, a short busy timeout,
and a progress-handler budget; extension loading stays off.
Previews are cut in SQL (`substr`, `length`), so a large value is never loaded to show
its first characters.

**What it shows.**

- **Tables:** tables, views, and internal tables (`sqlite_sequence`, `sqlite_stat*`,
  and, for an fsqlite snapshot, `fsqlite_meta` and `applied_tx`) in their own groups,
  with counts. A count past the budget is a lower bound.
- **Keys:** the rowid, or the primary key of a `WITHOUT ROWID` table.
  A view has no key, so it pages by position and says so.
- **Types:** the declared type and the affinity it implies, and the stored type when a
  value differs.
- **References:** declared foreign keys become `ref` fields and back-references; a
  reference to a missing row is drawn as missing.
- **Schema view:** each object’s DDL, indexes, triggers, and foreign keys.
- **Info view:** page size and count, encoding, journal mode, `user_version`,
  `application_id` (named when known, such as fsqlite’s `FSQL`), freelist size, the
  sidecars present, the access mode the reader chose and why, and the SQLite library
  version, flagging a write-ahead-log database read with a library older than 3.51.3,
  the release that fixes the WAL-reset bug.

**Generation.** For a rollback database, the main file’s identity, size, and
modification time plus the header’s change counter; for a write-ahead-log database, the
same plus the `-wal` file’s size and modification time.
The watch route reports the database with `-wal` and `-journal` as its sidecars.

**fsqlite stores.** A directory holding `fsqlite.json` is a `sqlite-store` kind (matched
by folder marker). It reads the snapshot `current` names, `immutable=1`, retrying when
garbage collection removes it between the two reads, shows the generation number, and
watches `current`. Pending transaction envelopes are counted in its Info view.
It is a thin source over the SQLite adapter.

### The Delimited and Record Sources

- **Delimited text** (`delimited` kind: `.csv`, `.tsv`) parses with the standard
  library’s `csv`, detects a header row, and infers field types from a bounded sample.
  A file under the parse cap is held in a per-generation cache with a sort index built
  on demand; a larger file shows its leading rows and says it is truncated.
  Views: Table (`V`) and Source (`S`).
- **Record lists** (`records` kind): a `.json`, `.yaml`, or `.yml` file whose top level
  is a list of mappings, matched by a content predicate at higher priority than the
  structured tree. Field descriptors come from the file’s SoftSchema contract when the
  contract registry resolves one, and are inferred from the records otherwise.
  Nested mappings and lists are `json` cells, drawn in the record with the structured
  plugin’s inline tree.
  Views: Table (`V`), Tree, and Source (`S`), so the existing tree stays one key away.

### The Table View

**Layout.** For a multi-table source, a list of tables on the left with counts and
groups; the grid in the main area; the record opening in place of the grid with a Back
path, as paraverse’s does.
A single-table source has no list.
The table, sort, filters, search, columns, scroll anchor, and open record live in the
view’s URL state, so a link reproduces the view and Back restores it.

**Grid.**

- Sticky header; columns from the descriptors; a column menu grouped into fields and
  references; chosen columns remembered per source.
- Fit to width by hiding default columns from the right, with a note naming how many are
  hidden; columns the reader chose never hide, and the first column pins when they
  overflow.
- Chrome in sans, literal values (keys, timestamps, hex, JSON) in mono, numbers in
  tabular numerals and right-aligned when the column is numeric.
- Cells clamp to two lines with the full text in the shared tooltip; `null` is muted; a
  stored-type mismatch carries a small marker.
- Enum, boolean, and reference values are links that add a filter; a reference is a chip
  with a hover card.
- Sorting from the header; a search box; per-column filters from the header menu; every
  active filter as a removable chip.
- Windowed rows using the object model’s list host if it has landed, otherwise the
  table’s own windowing, with measured row estimate and overscan.
  Search replaces native find over unmounted rows; copying a selection of rows yields
  TSV; printing prints the loaded rows.
  These replacements are stated as
  [Rendering Large Content](../../../large-content-rendering.md) requires.
- Keyboard: one Tab stop with roving focus, `j`/`k` or arrows to move, Enter to open,
  joining the shared row keyboard contract.

**Record.** Fields in schema order with full values (bounded per value), JSON through
the structured tree, blobs through the binary plugin’s hex view, references as chips,
and back-references grouped by referring table with a count and an “Open as table” link
that applies the `ref=` filter.

**Live behavior.** On `changed`, the view refetches the tables list and the current
window with the same query, coalescing bursts within one bounded window as
`createInventoryWatch` does.

- It keeps the scroll anchor, the focused row by key, open menus, and unsent filter
  text.
- Rows whose cells changed flash once in the data-motion color.
- New rows that would land above the viewport are offered (“3 new rows”), not inserted
  under the reader, following the arrival rule.
- A column or table that disappeared is dropped from the URL state with a notice.
- A **Live/Paused** pill lets a reader freeze a busy table; while paused, it counts the
  changes it is holding back.
- A source that reports **writer busy** keeps its last good rows on screen and says so,
  rather than replacing them with an error.

**Design system.** A new **Data Tables** section in
[the design system](../../../design-system.md) states these rules with the existing
tokens, and the shared component replaces the hand-built tables that use `.data-table`
today, so every table in the product looks and behaves the same.

### Security

Database content is untrusted input.
`trusted_schema=OFF` keeps functions in views and triggers from running with side
effects, a read fires no triggers, and the progress-handler budget stops an expensive
view or recursive query.
Text is rendered as text, never as HTML. Under the untrusted profile (repository
mirrors), the same routes serve, and immutable content is read through `immutable=1` or
deserialization.

## Key Decisions

### Decision 1: Where the Table Component Lives

- **A. A built-in `table` plugin that other plugins require.**
- **B. A core SDK surface (`mb.table`).**

**Recommendation: A.** It keeps core consumer-agnostic, makes the dependency explicit,
and is the first real exercise of declared dependencies.
If several unrelated features later need the grid, promoting it is a move, not a
rewrite.

### Decision 2: How Plugins Depend on Each Other

- **A. `requires` in the manifest and `mb.plugins.load(name)`,** replacing the
  render-time `mb.builtins` rule everywhere in one change.
- **B. Keep `mb.builtins` and document the table plugin’s namespace.**

**Recommendation: A.** The informal rule already needs a test to catch load-order
mistakes; a declared dependency lets the loader refuse them and the doctor report them.

### Decision 3: How a Plugin Claims a Binary Format

- **A. `magic` match rules on `[[kind]]`,** checked in `api_file` before the binary
  fallback.
- **B. A core-classified `sqlite` kind,** as `image` is.

**Recommendation: A.** It costs one rule type and unblocks every future binary format
plugin. B would repeat the LMDB problem for the next format.

### Decision 4: How an Open File Learns It Changed

- **A. A stat-polling watch route per open view** (`/api/watch`).
- **B. The inventory event stream** (`mb.onInventoryChange`).

**Recommendation: A.** B misses ignored files and paths deeper than its scope, and
databases are usually both.
A small per-view stat poll also works on mounts without filesystem events.
B remains the signal for the tree.

### Decision 5: A Write-Ahead-Log Database Whose Owner Is Not Running

- **A. A validated `immutable=1` read.**
- **B. `mode=ro`, accepting the sidecars it creates.**

**Recommendation: A.** B was measured to leave `-wal` and `-shm` beside someone else’s
database and to fail in a read-only folder.
A’s validation catches an owner that starts mid-read.

### Decision 6: Counts on Large Tables

- **A. Exact within the work budget, else a lower bound** marked as one.
- **B. Always exact.**

**Recommendation: A.** `count(*)` scans the table; a budget keeps a large table
responsive, and the envelope already says when a number is not final.

### Decision 7: A Read-Only Query Console

- **A. Defer.**
- **B. Ship a console** with `query_only`, an authorizer that permits only reads, and
  the same budget, drawn by the same grid.

**Recommendation: A** for this plan.
The grid, filters, and references cover browsing; a console is a separate surface with
its own parity and security review.

### Decision 8: Network Mounts and Sync Folders

- **A. Report, don’t guard:** the Info view states what the reader saw and chose, and
  errors map to busy, damaged, or changing states.
- **B. Copy first:** read a backup-API copy into memory when the file is under a size
  cap.

**Recommendation: A** now, with B as the follow-on if readers hit inconsistent reads on
mounts. Detecting a network mount reliably is platform-specific, and a copy of a large
database is expensive.

## Implementation Plan

Two phases, each one stack.

### Phase 1: The Table Plugin, Its Framework, and Text Sources

- [ ] Declared plugin dependencies: manifest `requires`, loader validation and ordering,
  `mb.plugins.load`, doctor report; move every `mb.builtins` consumer; update
  [Plugin Authoring](../../../plugins.md) and
  [Plugin System](../../architecture/arch-plugin-system.md)
- [ ] `PLUGIN_SDK_VERSION` bump with every built-in manifest updated
- [ ] Live reload for open files: `/api/watch`, `mb.watchFile`, shell wiring for every
  view; update [Live Updates](../../../browsing-files.md#live-updates)
- [ ] The table plugin: source protocol and registry, the five routes, the envelope,
  bounds measured and recorded
- [ ] The table view: grid, filters, search, sort, column fit, record view, hover cards,
  live behavior, URL state, keyboard
- [ ] Data Tables section in the design system; `.data-table` users moved to the
  component
- [ ] Delimited source and kind
- [ ] Record-list source and kind, SoftSchema-typed when a contract resolves
- [ ] Parity rows, `--show` and `--api` goldens, the browserless table session, the map
  in [Views, Models, and Routes](../../architecture/arch-views-models-routes.md),
  changelog fragments

### Phase 2: Live SQLite

- [ ] `magic` kind matching in `api_file`; file-type registry extensions and revision
- [ ] `sqlite_access.py`: admission, the access-choice table, connection settings,
  budget, error states; the GitHub catalog moved onto it
- [ ] SQLite source: tables, keys, typed cells, references and back-references, keyset
  paging, generation
- [ ] Schema and Info views
- [ ] Git-revision databases through deserialization under a cap
- [ ] fsqlite store kind
- [ ] Concurrency tests (below), goldens, parity rows, map updates, changelog fragment

## Testing Strategy

- **Goldens.** Each source has `--api` goldens over every table route and a `--show`
  golden for its kind.
  SQLite fixtures are built in each golden’s `before:` script from reviewable SQL text,
  not committed binaries, and cover rowid, `WITHOUT ROWID`, views, foreign keys, nulls,
  mixed stored types, blobs, long text, JSON text, and an fsqlite-marked database.
- **Nondestructive access tests**, each with a real writer in a second process: opening
  a write-ahead-log database with no sidecars creates no file; a read-only folder reads;
  a hot journal yields the busy state and leaves the journal untouched; a reader’s
  requests never stop a `wal_checkpoint(TRUNCATE)` from truncating; a commit changes the
  generation; an owner starting during a validated immutable read causes a retry.
  Directory listings before and after every test must match.
- **Browserless sessions** under `tests/dom/` drive the production table module through
  sort, filter, paging, opening a record, a live change that adds rows above and below
  the viewport, a removed column, pause and resume, and the busy state, with invariants
  on scroll anchor and focused key.
- **Bounds.** Each constant’s measurement is recorded beside it; a large generated table
  checks that a page costs an index seek, not a scan.
- **Paint-exempt rows** only for clamping, sticky positioning, and the flash, each named
  with its evidence in the
  [Parity Registry](../../architecture/arch-parity-registry.md).

## Rollout Plan

Both phases ship in the single artifact.
Phase 1 changes what `.csv`, `.tsv`, and record-list files open as by default, so its
changelog fragment says so.
Phase 2 changes what `.sqlite` and SQLite `.db` files open as.
The SDK version bump in Phase 1 is a hard gate for installed plugins, as intended.

## Open Questions

- Should a directory of SoftSchema records sharing one contract open as one table, as a
  knowledge base’s folders would?
  The protocol supports it; the open question is the kind rule and the cost of reading
  every file.
- Should JSONL logs gain a Table view beside the Log view?
- Should the Info view offer a consistent copy to a file of the reader’s choosing
  (backup API), as an explicit action?
- Should hover cards and the record view show an image when a blob or URL field holds
  one?

## References

- [paraverse](https://github.com/jlevy/paraverse): `db/src/paraverse_graph/` (the
  browser, `schemas.py`, `web/js/table.js`, `web/js/record.js`, `web/style.css`)
- [fsqlite](https://github.com/jlevy/fsqlite): the format specification and the portable
  concurrent SQLite research
- SQLite: [URI filenames](https://sqlite.org/uri.html),
  [WAL](https://sqlite.org/wal.html), [file format](https://sqlite.org/fileformat.html),
  [backup API](https://sqlite.org/backup.html)
- [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md)
- [Plugin System](../../architecture/arch-plugin-system.md),
  [Live Delivery](../../architecture/arch-live-delivery.md),
  [Parity Registry](../../architecture/arch-parity-registry.md)
- [Rendering Large Content](../../../large-content-rendering.md),
  [Design System](../../../design-system.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
