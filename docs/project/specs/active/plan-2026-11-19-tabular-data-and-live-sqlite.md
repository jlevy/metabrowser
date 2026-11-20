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
- **Record lists:** a JSON or YAML file whose top level is a list of mappings.
- **SQLite:** any SQLite database, including one another application is writing at that
  moment, read without changing it, with its writes shown as they land.

The table plugin knows nothing about any source.
A source answers a small set of questions (what tables exist, what their fields are,
which rows match a query, what one record holds), and every source is drawn, queried,
tested, and reached from `metab` the same way.

The look follows the knowledge-base browser in
[paraverse](https://github.com/jlevy/paraverse) (`db/src/paraverse_graph/web/`), which
already presents typed records over a graph database through a source-neutral JSON
contract. The approach for reading live databases follows the SQLite research in
[fsqlite](https://github.com/jlevy/fsqlite) and the measurements recorded in
[Reading Another Application’s SQLite Database](../../../../explorations/sqlite-guest-reads/README.md).

## Goals

- **One table experience** for every tabular source: typed columns, server-side sort,
  typed filters and search, keyset paging over arbitrarily large tables, a record view,
  and references drawn as links with hover cards.
- **Clean presentation of all the data.** Every value is visible: nulls are distinct
  from empty strings, a value whose stored type differs from its column’s declared type
  says so, an integer past what a browser number holds keeps its digits, and long text
  and blobs are previewed in the table and shown in the record.
- **Strictly nondestructive SQLite.** Opening a database never writes to it or its log,
  never creates a file beside it, never rolls back another process’s journal, and takes
  no lock where a lock-free read is valid; where one is not, a lock lasts at most a
  short deadline. Reading through a live log’s wal-index updates its shared read marks,
  as every SQLite reader does.
  Two effects can be detected and reported but not prevented: an owner that exits
  between the reader’s check and its open, and a reader still open when the owner
  closes, which keeps the owner from deleting its `-wal` and `-shm`. Every connection
  lives for one request to keep both rare.
- **Live.** An open table refreshes when its file changes, including a database whose
  owner is writing through a write-ahead log, while keeping the reader’s scroll
  position, focused row, and unsent filter text.
- **Reusable by construction.** A source plugin declares that it requires the table
  plugin and declares its source adapter in its manifest; installed plugins can add
  sources the same way.
- **CLI parity.** Every route is reachable through `metab --api` and pinned by goldens,
  every table has an address `metab --show` can name, and the table’s browser state
  machine runs browserlessly, as
  [AGENTS.md](../../../../AGENTS.md#cli-and-functional-ui-parity) requires.
- **Level up the framework where this needs it**: declared plugin dependencies, plugin
  kinds for binary formats, and file watches on the page’s existing event stream.
  The server, shell, and built-in plugins ship together, so each framework change lands
  with every consumer updated in the same change, with no compatibility layer.

## Non-Goals

- **Editing.** Every source is read-only.
  Writing rows belongs with the trusted editing plan, not here.
- **Arbitrary SQL.** A read-only query console is
  [Decision 7](#decision-7-a-read-only-query-console), deferred.
- **Reload on change for other views.** Markdown, source, and the structured tree each
  need their own rule for scroll, selection, expanded nodes, and loaded chunks; that is
  its own plan, which can reuse the file watches built here.
- **Other database engines.** DuckDB, LMDB, and Parquet follow the same source recipe
  later, each as its own plugin when a consumer appears.
- **A directory of record files as one table**, and record lists typed by a SoftSchema
  contract: [open questions](#open-questions).
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
  Tables are hand-built: the folder Distribution and totals views draw
  `file-type-summary-table`, and the `.data-table` rules in `static/styles.css` have no
  user. Windowing is implemented separately by the structured tree, the Pulls panel, the
  ref selector, and the diff summary.
- **A plugin cannot claim a binary file.** `api_file` classifies directories, JSONL,
  images, and text, and sends everything else to `binary`; plugin `[[kind]]` rules see
  only text and JSONL ([Plugin System](../../architecture/arch-plugin-system.md)).
  Content sniffing (`content_sniff.py`) decides only text versus binary.
  The file-type registry lists `sqlite` under its own kind and `db` under
  `configuration`.
- **A file can already be a container.** A kind that declares
  `container = { children = "<route>" }` gets a chevron in the tree, its children as
  rows, and an address for each child (`<file>/<inner>`), on the served folder and on a
  Git pin
  ([Navigation Containers](../../architecture/arch-plugin-system.md#navigation-containers)).
- **Plugins share helpers informally.** A built-in publishes `mb.builtins.<name>` and a
  consumer reads it only at render time, after awaiting the provider kind’s assets
  ([Render-Time-Only Namespace Rule](../../../plugins.md#render-time-only-namespace-rule)).
  Nothing declares the dependency, so nothing checks it.
- **An open file does not refresh.**
  [Live Updates](../../../browsing-files.md#live-updates) says an open file shows new
  content on reopen or reload; only files under `.logs` and `.state` with a few
  extensions auto-reload.
  The page’s one `/api/events` stream carries tree entries only to depth two and catalog
  deltas only for unignored files, so nothing signals a change to an ignored file.
- **SQLite is already read safely in one place.** The GitHub plugin’s pull request
  catalog (`builtin_plugins/github/pull_catalog.py`) checks the 100-byte header, opens
  `mode=ro`, sets `trusted_schema=OFF`, `query_only`, and `SQLITE_LIMIT_LENGTH`, bounds
  work with a progress handler, and classifies damaged versus transient errors.
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
  reload that repairs the URL when a column disappears, and one flash that means “the
  data changed,” distinct from interface motion.

What stays out: its conference-specific kind groups, default columns and card fields,
its typed-ID prefix maps, and any per-dataset logic.
Two choices change for databases: paraverse renders null as blank, but in a database
null and the empty string differ and must look different; and paraverse renders every
row of a page with offset paging, which does not scale to a million-row table.

### Reading Another Application’s Database

A viewer pointed at a browser’s history database or an application’s state database is a
guest.
[Reading Another Application’s SQLite Database](../../../../explorations/sqlite-guest-reads/README.md)
records the measurements behind the access rules, with the script that reruns them.
What they establish:

- **Which sidecars exist does not say what to read.** What matters is whether `-wal`
  holds frames. `immutable=1` over a non-empty `-wal` silently drops committed rows, and
  a table the owner created but has not checkpointed is missing entirely.
  A crashed owner leaves `-wal` and `-shm` behind just as a live one does.
- **`mode=ro` writes beside the database in three states:** it creates `-wal` and `-shm`
  for an idle write-ahead-log database and leaves them, creates `-shm` beside a `-wal`
  that has none, and rewrites a stale `-shm`. In a read-only folder the first two fail.
- **The path matters.** SQLite looks for sidecars beside the resolved file, so a symlink
  in another folder hides them from a stat beside the link, and a second hard link gets
  sidecars of its own and silently misses the owner’s log.
  An owner that exits between the reader’s stat and its open turns a correct `mode=ro`
  into one that creates sidecars.
- **A reader can hold up the owner.** A held read transaction starves the owner’s
  checkpoint until it ends.
  In rollback-journal mode a reader’s shared lock refuses an owner’s commit outright
  when the owner sets no busy timeout, SQLite’s default; a viewer sorting a table by an
  unindexed column failed up to a quarter of a fast writer’s commits.
  A validated `immutable=1` read takes no lock and failed none, but it succeeds only
  when it is shorter than the gap between commits.
- **A hot `-journal` is a half-written file.** `mode=ro` refuses it with
  `SQLITE_READONLY_ROLLBACK`; `immutable=1` reads the half-written rows.
- **A commit in write-ahead-log mode leaves the main file untouched**, so a change
  detector that stats only the database misses every commit until a checkpoint.

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
   model, and the routes.
   It has no kind of its own.
2. **Source plugins** (`delimited`, `sqlite`, and a Table view for the structured
   plugin’s record lists), each declaring `requires = ["table"]` and its source adapter.
3. **Framework improvements** in core that the layers need and that every plugin gains:
   declared dependencies, the source protocol types, binary kinds by magic number, and
   file watches on the page’s event stream.

```
 browser                          server
 ┌────────────────────────┐       ┌──────────────────────────────────────────┐
 │ table view (table/)    │ HTTP  │ /api/plugin/table/{tables,schema,rows,   │
 │  grid · record         │──────▶│                     record,card}         │
 │  query state in URL    │       │   └─ [[table_source]]: kind → adapter    │
 │                        │       │        ├─ delimited  (csv, tsv)          │
 │ live: mb.watchFile ◀───┼───────│ /api/events  ├─ records (json, yaml)     │
 └────────────────────────┘  SSE  │  file.changed └─ sqlite (sqlite_access)  │
                                  └──────────────────────────────────────────┘
```

### The Source Protocol

A source adapter is a Python object the table routes call with a bounded handle on one
file. It answers:

| Method | Returns |
| --- | --- |
| `tables()` | Each table: `id`, `label`, `group` (`tables`, `views`, `virtual`, `internal`), `count` (exact or a lower bound), and whether it has a stable row key |
| `schema(table)` | Field descriptors, the key fields, the default columns, outgoing references, and incoming references (other tables’ fields that point here) |
| `rows(table, query)` | One page in the collection envelope |
| `record(table, key)` | Every field’s value, previewed past the value bound, with references resolved |
| `card(table, key)` | A short summary for a hover card: label, a few fields |
| `generation()` | An opaque token that changes whenever the source’s content may have changed |

**Where it lives.** The protocol types and the wire contract are a core module
(`metabrowser.table_source`), re-exported from `metabrowser.plugin_api`, and are SDK
surface under `PLUGIN_SDK_VERSION`. The table plugin owns only the component and the
routes, so core imports no plugin.

**How a source registers.** A manifest declares it, as kinds, views, and data hooks are
declared, so `metab --doctor` and the parity check see it:

```toml
[[table_source]]
kind = "sqlite"
adapter = "metabrowser.builtin_plugins.sqlite.source:adapter"
```

The adapter is recorded as text and imported on first use.
Only a built-in or an installed distribution can declare one, since operator-directory
plugins run no Python.
Adapters are synchronous and run on the route threadpool, as sidekicks do today.

**The handle.** An adapter reads through a `ContentRef`, as every hook does, plus an
optional local-path capability: the resolved real path of a file on the served folder.
SQLite needs the path for its sidecars; on a Git pin there is no path, and the SQLite
source deserializes the blob instead.
A text source needs only the bytes.

**Field descriptor.** One shape, adapted from paraverse’s:
`{name, title, type, declared_type, nullable, key, hidden, generated, list, enum, format, ref, sortable, sort_note, filterable, numeric}`.
`type` is one of `text`, `integer`, `real`, `boolean`, `date`, `datetime`, `json`,
`blob`, or `unknown`. `ref` is `{table, fields, to}`, field lists on both sides, so a
composite foreign key is one reference.
`sortable` is false where a sort would scan a large table, and `sort_note` says why.
A source fills in what it knows and leaves the rest null; the client derives nothing a
source could have stated.

**Cell encoding.** A cell is a scalar, or an envelope when a scalar would hide or lose
something:

- `null` is JSON null, drawn as a muted `null`; the empty string is drawn as empty.
- `{int: "<decimal>"}` for an integer outside ±(2⁵³ − 1), which a browser number would
  round; `{real: "inf"}`, `"-inf"`, or `"nan"` for a value JSON cannot carry.
- `{text, length}` for text longer than the preview, cut on the server, and
  `{blob, length, hex}` for bytes; `invalid_utf8: true` marks text that was not valid
  UTF-8, decoded with replacement characters.
- `{length, preview: false}` for a value too large to preview where the source cannot
  read part of it, and `{error}` for one the source refused, so one value never fails
  the page.
- `{json, preview}` for a JSON value in a text column the schema calls `json`.
- `{ref: {table, key, label}}` for a reference, resolved for the whole page in one
  batched read.
- `{value, stored}` when a value’s stored type differs from the declared type (SQLite’s
  dynamic typing: text in an `INTEGER` column), so the table shows it rather than
  coercing it.

**Keys.** A record’s `key` is an opaque token the source mints, as `after` is, so a
composite or blob primary key needs no client encoding.

**Query.** One wire shape for every source: `sort`, `order`, `q` (search), typed filters
`f.<field>=<op>:<value>` (`eq`, `ne`, `lt`, `le`, `gt`, `ge`, `null`, `notnull`,
`contains`), `ref=<table>:<key>` (rows that reference one record), `cols`, `after`, and
`limit`. Sort is one `sortable` field plus the row key as a tie-breaker, so paging is
stable. Search matches text fields only and says which fields it searched.

**Envelope.** The collection convention from the object model draft:
`{rows, next_after, complete, truncated, generation}` plus `columns`, `count`,
`count_complete`, and `estimate`.

- `after` is an opaque cursor the source minted; one minted under one generation stays
  valid under the next, since it names a position in sort order, not an offset.
- A count is exact up to a cap and otherwise a lower bound, drawn as “at least
  1,000,000”. `estimate` is a cheap number a source may add beside a lower bound, such
  as SQLite’s `sqlite_stat1` row count or largest rowid, drawn as approximate.
- A filter or search that runs out of budget returns the rows it found in key order with
  `complete: false` and the number of rows it examined; a sort cannot be returned in
  part, so it returns a refusal state naming the field.

**Rows and objects.** Rows are not objects in the object model’s sense: they have no
type, contract, or store entry, and the hover card is the table’s own.
The only shared surface is the collection envelope’s five keys and the arrival rule.

**Bounds.** Every route is bounded by named constants defined beside their code and
listed in [Rendering Large Content](../../../large-content-rendering.md): rows per page,
characters per cell preview, bytes per record value, references resolved per page, a
count cap, the row count past which an unindexed sort is refused, and a work budget per
request (a wall-clock deadline for every source, plus SQLite opcodes through a progress
handler). Each value is set from a measurement recorded beside the constant, per the
repository’s
[measure-before-bounding rule](../../../../AGENTS.md#browser-and-plugin-boundary).

### Routes, Addresses, and the CLI

The table plugin owns one route set, and every source answers through it:

| Route | Serves |
| --- | --- |
| `GET /api/plugin/table/tables?path=` | The source’s tables with counts and groups; also the container children hook |
| `GET /api/plugin/table/schema?path=` | Field descriptors, keys, references, defaults |
| `GET /api/plugin/table/rows?path=&…query` | One page in the collection envelope |
| `GET /api/plugin/table/record?path=&key=` | One record in full, with back-references counted |
| `GET /api/plugin/table/card?path=&key=` | A hover card |

The kind of the file at `path` selects the adapter, so a new source adds no route.

**A database is a container**
([Decision 9](#decision-9-how-a-database-exposes-its-tables)): the SQLite and fsqlite
kinds declare `container = { children = "tables" }`. The tree lists a database’s tables
and views as its children, so `app.db` is the database’s Info and Schema overview and
`app.db/users` is one table, an address that works on a Git pin as every container’s
does. A single-table source (a CSV file, a record list) is its own table.
Sort, filters, search, columns, and the open record (`record=<key>`) are query state on
the table’s address, the same for every source; a record is not a path segment, since
its key is an opaque token.
`metab --show app.db/users` and the `--api` goldens name tables by the same addresses.

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
Every classification site checks it: `api_file` after images and before the binary
fallback, reading only the sniff prefix it already reads; `classify_identity` for a Git
blob, from the prefix the caller already holds; `_resolve_container_child`; and
`metab --show`. The SQLite kind matches `SQLite format 3\0` at offset 0 with extensions
`.sqlite`, `.sqlite3`, `.db`, `.db3`, and `.s3db`; a `.db` file that is not SQLite stays
binary. Magic is checked on the bytes on disk, so a compressed database (`x.sqlite.gz`)
stays binary.
The file-type registry moves `db` from `configuration` to the `sqlite` kind
and adds the other extensions, with a revision bump.
This also lets a future installed plugin claim LMDB or Parquet without a core change.

**File watches on the event stream**
([Decision 4](#decision-4-how-an-open-file-learns-it-changed)).
`mb.watchFile(path, {onChange})` registers a path for the page’s existing `/api/events`
connection and returns a disposer.
The server resolves the real path and its sidecars, stat-polls the registered paths the
inventory does not already deliver (ignored or deeper than the stream’s scope) on a
bounded interval, and sends one `file.changed` event with the new generation, coalescing
bursts. Registered paths per connection are bounded by a named constant.
The shell’s page-connections owner (`shell.page-connections`) keeps it, so a page still
holds one stream. On a Git pin `/api/events` answers `unsupported_for_subject` and a
pinned file cannot change, so there is nothing to watch.
`/api/stream` stays the JSONL log tail; the two do not interact.

### The SQLite Source

**Shared access helper.** `src/metabrowser/sqlite_access.py` holds the one way the
product opens a database it does not own: header admission, the access choice below,
connection settings, the work budget, and error classification.
The GitHub catalog moves onto it in the same change.

**Choosing how to open.** The helper resolves the path’s real file first and stats its
sidecars beside that file, then decides from the 100-byte header and those stats before
SQLite touches anything:

| Header and sidecars at the real path | Open | Shown as |
| --- | --- | --- |
| Rollback journal, no `-journal` or a zero-byte one | `immutable=1`, validated; after a failed validation and one retry, `mode=ro` under the deadline | Current |
| Rollback journal, a non-empty `-journal` | `mode=ro`; `SQLITE_READONLY_ROLLBACK` is the state **writer busy or interrupted** | Busy |
| Write-ahead log, no `-wal` or a zero-byte one | `immutable=1`, validated | Current |
| Write-ahead log, `-wal` with frames, `-shm` present, one hard link | `mode=ro`, with the race check below | Current |
| Write-ahead log, `-wal` with frames, and no `-shm` or more than one hard link | `immutable=1`, validated | The checkpointed state, with “N bytes of write-ahead log not included” |
| Immutable content: a Git revision, an fsqlite snapshot | `immutable=1`, or deserialized into memory under a size cap with header bytes 18 and 19 set to rollback mode | Current; a committed write-ahead-log database is shown without its log |

- **Validated** means the file’s identity, size, modification time, and header change
  counter match before and after the read and no journal or log frames appeared.
  A failed validation is retried once and then reported as changing, except where the
  table names a fallback.
- **The race check.** Before connecting, the helper opens the `-shm` it saw, read-only,
  and after connecting compares that file’s identity with the path’s, as
  `pull_catalog._database` already does for the main file.
  If the owner exited in between and the open created sidecars, the Info view says so.
- **fsqlite transients** (`.build-*`, `.direct-*`, `.work-*`) are live rollback-journal
  builds; they never take the `mode=ro` fallback.

**Every request is short.** Each route call opens a fresh connection, reads inside one
short transaction, and closes it; no connection or transaction outlives a request.
A watchdog calls `Connection.interrupt()` at the request’s deadline, beside the
progress-handler budget, since `count(*)` runs a handful of opcodes and never reaches a
progress handler.

- **Counts** run as `SELECT count(*) FROM (SELECT 1 FROM t LIMIT :cap + 1)`, which the
  budget can stop and which yields “at least cap” directly.
- **Paging** is keyset by the sort value and the row key.
  It is an index seek only in key order (the rowid or primary key) or on a column that
  leads an index; past the measured row count, `schema()` marks every other field
  unsortable and says why.
  A null cursor continues on its own branch (`(s IS NULL AND id > ?) OR s IS NOT NULL`),
  since a row-value comparison with null is unknown; with that branch, pages match one
  `ORDER BY` over mixed types and nulls exactly.
- **Filters and search** are scans by nature and return partial results under the budget
  as the envelope describes.

**Connection settings,** each a named constant: `query_only`, `trusted_schema=OFF`,
`SQLITE_DBCONFIG_DEFENSIVE`, `cell_size_check=ON`, `mmap_size=0`, a small cache, a short
busy timeout, limits on value length, SQL length, columns, expression depth, and
attached databases, and an authorizer that allows only `SELECT`, reads, the functions
the adapter itself emits, and the pragmas it uses, denying everything else, `ATTACH`
included. Extension loading stays off.

**Values.** The adapter reads `octet_length` and `typeof` first; `length` and `substr`
load the whole value.
A value over the measured preview threshold is previewed through `Connection.blobopen`,
which reads part of a text or blob in a rowid table; in a `WITHOUT ROWID` table or a
view, where `blobopen` is unavailable, the cell shows the size alone.
`SQLITE_LIMIT_LENGTH` stays as a backstop, and its error becomes the cell’s `{error}`.
Text is read as bytes and decoded with replacement.
The record route applies the same rules.

**What it shows.**

- **Tables:** tables, views, and virtual tables in their own groups, and internal tables
  (`sqlite_sequence`, `sqlite_stat*`, virtual tables’ shadow tables, and, for an fsqlite
  snapshot, `fsqlite_meta` and `applied_tx`) under `internal`, each with a count.
  A virtual table is never queried under the untrusted profile, and elsewhere only when
  the library is at or past the minimum the code names.
- **Columns** come from `table_xinfo`, so hidden and generated columns show; a `STRICT`
  table is marked; a table whose own columns shadow `rowid` keys by another alias or by
  its primary key.
- **Keys:** the rowid, or the primary key of a `WITHOUT ROWID` table.
  A view has no key, so it pages by position and says so.
- **Types:** the declared type and the affinity it implies, and the stored type when a
  value differs.
- **References:** declared foreign keys become `ref` fields and back-references; a
  reference to a missing row is drawn as missing.
- **Schema view:** each object’s DDL, indexes, triggers, and foreign keys.
- **Info view,** from pragmas on the connection, since the main file’s header is stale
  while a log holds frames: page size and count, encoding, journal mode, `user_version`,
  `application_id` (named when known, such as fsqlite’s `FSQL`), freelist size, the
  sidecars and the log’s size, the access mode chosen and why, and the SQLite library
  version read against a table in code of library versions and what each means for a
  reader.

**Generation.** For a rollback database, the main file’s identity, size, and
modification time plus the header’s change counter; for a write-ahead-log database, the
same plus the `-wal` file’s size, modification time, and header checkpoint sequence and
salts (bytes 12 to 24), which change every time the log restarts even when its size
repeats. The watch reports the database with `-wal` and `-journal` as its sidecars.

**fsqlite stores.** The store’s `fsqlite.json` is the `sqlite-store` kind:
`folder_marker = "fsqlite.json"` with `json_has_key = "format"` and
`json_value_prefix = "fsqlite"`, so the folder gets its badge and opening the marker
opens the store, with no core change.
It reads the snapshot `current` names, `immutable=1`, retrying when garbage collection
removes it between the two reads, shows the generation number, and watches `current`.
Pending transaction envelopes are counted in its Info view.
It is a thin source over the SQLite adapter and a container like any database.

### The Delimited and Record Sources

**Delimited text** (`delimited` kind: `.csv`, `.tsv`) parses with the standard library’s
`csv` under these rules:

- The extension sets the delimiter (comma or tab); quoting is RFC 4180’s double quote.
- Bytes are UTF-8 with a leading byte-order mark dropped; invalid bytes are replaced and
  the cell marked `invalid_utf8`.
- The first row is the header.
  An empty name becomes `column_<n>` and a repeated one gains `_<n>`.
- A short row’s missing cells are absent, drawn apart from empty; a long row’s extra
  cells go to one trailing `extra` field.
- Types are inferred from a bounded sample; a later value that contradicts its column’s
  type is a `{value, stored}` cell.
- A file under the parse cap is held in a per-generation cache, bounded in bytes and
  entries, with a sort index built on demand.
  A larger file shows its leading rows; its sort, filter, and count say they cover only
  those rows (`complete: false`).

Views: Table (`V`) and Source (`S`).

**Record lists** are a Table view of the structured plugin’s `structured` kind, beside
Tree and Source, reading the `parsed` hook’s result under its existing bound.
A view is a tab on every file of its kind, so the Table tab draws a top-level list of
mappings and, for any other document, says it is not a list of records; Tree stays the
default. Fields are inferred from the records.
Nested mappings and lists are `json` cells, drawn in the record with the structured
plugin’s inline tree.
This needs no new kind or content predicate; a dedicated kind would need a list
predicate that, under the classifier’s byte bounds, would miss exactly the large files
that most need a table.

### The Table View

**Layout.** The grid fills the view, and the record opens in place of the grid with a
Back path, as paraverse’s does.
A database’s tables are its rows in the tree, not a second list inside the view.
The table, sort, filters, search, columns, scroll anchor, and open record are the URL’s:
the address names the table, and the query carries the rest, so a link reproduces the
view and Back restores it.
Columns the reader chose live only there.

**Grid.**

- Sticky header; columns from the descriptors; a column menu grouped into fields and
  references.
- Fit to width by hiding default columns from the right, with a note naming how many are
  hidden; columns the reader chose never hide, and the first column pins when they
  overflow.
- Chrome in sans, literal values (keys, timestamps, hex, JSON) in mono, numbers in
  tabular numerals and right-aligned when the column is numeric.
- Cells clamp to two lines with the full text in the shared tooltip; `null` is muted; a
  stored-type mismatch carries a small marker.
- Enum, boolean, and reference values are links that add a filter; a reference is a chip
  with a hover card.
- Sorting from the header of a sortable column; a search box; per-column filters from
  the header menu; every active filter as a removable chip.
- **Windowing** ([Decision 11](#decision-11-windowing-the-grid)): a table under a
  measured row count is drawn whole and keeps native find, copy, and print.
  A larger table uses the grid’s own fixed-row-height window with measured overscan,
  where search is the stated replacement for native find, copying a selection of rows
  yields TSV, and printing prints the loaded rows, as
  [Rendering Large Content](../../../large-content-rendering.md) requires.

**Accessibility.**

- A table drawn whole is a `<table>` with `scope="col"` headers and `aria-sort`. A
  windowed grid has `role="grid"`, `aria-rowcount` (`-1` while the count is a lower
  bound), `aria-rowindex` on each row, and `aria-sort` on the sorted header.
- One Tab stop with roving focus: Up and Down (or `j`/`k`) move between rows and Left
  and Right between cells, so a reference chip or a filtering value is reachable.
  Enter on a cell follows its link; Enter on the row opens the record.
  A hover card also opens on focus.
  This joins the shared row keyboard contract.
- “3 new rows”, Paused, and writer busy are announced through one polite live region.

**Record.** Fields in schema order with their values (previewed past the value bound),
JSON through the structured tree, blobs through the binary plugin’s hex view, references
as chips, and back-references grouped by referring table with a count and an “Open as
table” link that applies the `ref=` filter.

**Live behavior.** On `file.changed`, the view refetches the current window with the
same query, coalescing bursts within one bounded window as `createInventoryWatch` does.

- It keeps the scroll anchor, the focused row by key, open menus, and unsent filter
  text.
- Rows whose cells changed flash once in `--row-flash-bg`, following
  [Live Row Arrivals](../../../design-system.md#live-row-arrivals) and its
  reduced-motion treatment.
- New rows that would land above the viewport are offered (“3 new rows”), not inserted
  under the reader, following the arrival rule.
- A column or table that disappeared is dropped from the URL state with a notice.
- A **Live/Paused** pill lets a reader freeze a busy table; while paused, it counts the
  changes it is holding back.
- A source that reports **writer busy** keeps its last good rows on screen and says so,
  rather than replacing them with an error.

**Design system.** A new **Data Tables** section in
[the design system](../../../design-system.md) states these rules with the existing
tokens, extending Live Row Arrivals to changed rows.
The folder Distribution and totals tables (`file-type-summary-table`) adopt its rules,
and the unused `.data-table` CSS is deleted, so every table in the product looks the
same.

### Security

Database content is untrusted input, and a crafted database reaches SQLite’s parser and
every compiled-in virtual-table module through tables it controls.
The connection settings above are the defense: `trusted_schema=OFF` keeps functions in
views and triggers from running, `DEFENSIVE` and `cell_size_check` guard against a
corrupt file, the authorizer admits only reads, a read fires no triggers, and the budget
and deadline stop an expensive view or recursive query.
Virtual tables are listed but never queried under the untrusted profile (repository
mirrors), where immutable content is read through `immutable=1` or deserialization.
Text is rendered as text, never as HTML. The SQLite phase gets a dedicated security
review.

## Key Decisions

### Decision 1: Where the Table Component Lives

- **A. A built-in `table` plugin that other plugins require.**
- **B. A core SDK surface (`mb.table`).**

**Recommendation: A.** It keeps the component out of core, makes the dependency
explicit, and is the first real exercise of declared dependencies.
The source protocol types are core either way, since installed plugins implement them.
If several unrelated features later need the grid, promoting it is a move, not a
rewrite.

### Decision 2: How Plugins Depend on Each Other

- **A. `requires` in the manifest and `mb.plugins.load(name)`,** replacing the
  render-time `mb.builtins` rule everywhere in one change.
- **B. Keep `mb.builtins` and document the table plugin’s namespace.**

**Recommendation: A.** The informal rule already needs a test to catch load-order
mistakes; a declared dependency lets the loader refuse them and the doctor report them.

### Decision 3: How a Plugin Claims a Binary Format

- **A. `magic` match rules on `[[kind]]`,** checked at every classification site before
  the binary fallback.
- **B. A core-classified `sqlite` kind,** as `image` is.

**Recommendation: A.** It costs one rule type and unblocks every future binary format
plugin. B would repeat the LMDB problem for the next format.

### Decision 4: How an Open File Learns It Changed

- **A. A stat-polling watch stream per open view** (`/api/watch`).
- **B. The inventory event stream as it is** (`mb.onInventoryChange`).
- **C. File watches registered on the page’s existing `/api/events` connection.**

**Recommendation: C.** The server speaks HTTP/1.1, so a browser shares six connections
per origin across every tab; before the page-connections owner, the sixth page waited 55
to 56 seconds for one ([Parity Registry](../../architecture/arch-parity-registry.md),
`shell.page-connections-browser`). A puts a second standing stream on every page that
shows a table. B misses ignored files and paths deeper than its scope.
C adds one event and a bounded registration to the stream the page already holds.

### Decision 5: A Write-Ahead-Log Database With No Frames in Its Log

- **A. A validated `immutable=1` read.**
- **B. `mode=ro`, accepting the sidecars it creates.**

**Recommendation: A.** B leaves `-wal` and `-shm` beside someone else’s database and
fails in a read-only folder.
A is valid only while the log is absent or empty before and after the read; a log with
frames is read with `mode=ro` through its wal-index, or shown as not included when that
would write.

### Decision 6: Counts on Large Tables

- **A. Exact up to a cap, else a lower bound** marked as one, from a capped subquery
  under the budget and deadline.
- **B. Always exact.**

**Recommendation: A.** A count scans the table; a cap keeps a large table responsive,
and the envelope already says when a number is not final.

### Decision 7: A Read-Only Query Console

- **A. Defer.**
- **B. Ship a console** with `query_only`, the reads-only authorizer, and the same
  budget, drawn by the same grid.

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

### Decision 9: How a Database Exposes Its Tables

- **A. The database kind is a navigation container** whose children are its tables and
  views.
- **B. A list of tables inside the view,** with the table in view URL state.

**Recommendation: A.** The container contract already gives a file children in the tree,
an address per child, views that receive `container_inner`, and Git-pin support.
B would duplicate the tree, give a table no address of its own, and leave `metab --show`
nothing to name a table by.

### Decision 10: Reading a Rollback-Journal Database

- **A. Lock-free first:** a validated `immutable=1` read, falling back to `mode=ro`
  under the request deadline only when validation fails twice.
- **B. `mode=ro` always,** with each read’s lock bounded by the deadline and refreshes
  spaced by their cost.

**Recommendation: A.** A reader’s shared lock refuses an owner’s commit when the owner
sets no busy timeout, and live refresh reads exactly when the owner is writing.
A validated read took no lock and failed no commits in the measurements; refusing
unindexed sorts on large tables keeps reads short enough to validate, and the deadline
bounds the fallback.

### Decision 11: Windowing the Grid

- **A. The table owns a fixed-row-height grid window now,** with a tracked follow-up to
  converge with the object model’s list host once that lands.
- **B. Wait for the list host.**

**Recommendation: A.** The list host is an unapproved draft that draws variable-height
rows, not a column grid, and B would hold the owner’s main goal behind it.

## Implementation Plan

Six phases, each one stack and each accepted on its own, so live SQLite does not wait on
everything else.

### Phase 1: Declared Plugin Dependencies

- [ ] Manifest `requires`, loader validation and ordering, `mb.plugins.load`, doctor
  report; move every `mb.builtins` consumer; update
  [Plugin Authoring](../../../plugins.md) and
  [Plugin System](../../architecture/arch-plugin-system.md)
- [ ] `PLUGIN_SDK_VERSION` bump with every built-in manifest updated

### Phase 2: The Table Plugin and Delimited Text

- [ ] Source protocol types and wire contract in core; `[[table_source]]` declarations
- [ ] The five routes, the envelope, bounds measured and recorded
- [ ] The table view: grid, windowing, filters, search, sort, column fit, record view,
  hover cards, URL state, keyboard, accessibility
- [ ] Data Tables section in the design system; folder tables adopt it; `.data-table`
  deleted
- [ ] Delimited source and kind
- [ ] Parity rows, `--show` and `--api` goldens, the browserless table session, the map
  in [Views, Models, and Routes](../../architecture/arch-views-models-routes.md),
  changelog fragment

### Phase 3: Static SQLite

- [ ] `magic` kind matching at every classification site; file-type registry move and
  revision
- [ ] `sqlite_access.py`: admission, the access table, the race check, connection
  settings, authorizer, budget and deadline, error states; the GitHub catalog moved onto
  it
- [ ] SQLite source as a container: tables, keys, typed cells, references and
  back-references, keyset paging, sortability, capped counts
- [ ] Schema and Info views; Git-revision databases through deserialization under a cap
- [ ] Nondestructive access tests, goldens, parity rows, map updates, changelog
  fragment; dedicated security review

### Phase 4: Live Tables

- [ ] File watches on `/api/events`: registration, `file.changed`, `mb.watchFile`,
  bounded paths, under `shell.page-connections`
- [ ] Generation tokens for every source; the table’s live behavior; the contention test

### Phase 5: Record Lists

- [ ] The Table view of the `structured` kind, with goldens and parity

### Phase 6: fsqlite Stores

- [ ] The `sqlite-store` kind, snapshot reads, generation, goldens

## Testing Strategy

- **Goldens.** Each source has `--api` goldens over every table route and a `--show`
  golden for its kind and for a table’s address.
  SQLite fixtures are built in each golden’s `before:` script from reviewable SQL text,
  not committed binaries, and cover rowid, `WITHOUT ROWID`, views, virtual tables,
  composite and blob primary keys, composite foreign keys, nulls in a sorted column,
  mixed stored types, integers past 2⁵³, infinite reals, invalid UTF-8 text, blobs, long
  text, JSON text, hidden and generated columns, a `STRICT` table, and an fsqlite-marked
  database.
- **Nondestructive access tests**, grown from the
  [exploration’s cases](../../../../explorations/sqlite-guest-reads/README.md#access),
  each with a real owner in a second process and a directory listing before and after:
  an idle write-ahead-log database creates nothing; a read-only folder reads; a crashed
  owner’s `-wal` with and without `-shm`, writable and read-only, reads or reports the
  log not included; an owner’s new table not yet checkpointed shows; an owner that exits
  between the stat and the open is reported; a symlink in another folder and a second
  hard link read the right state; a hot journal yields the busy state and leaves the
  journal untouched; a reader’s requests never stop a `wal_checkpoint(TRUNCATE)`; a
  commit changes the generation; an owner starting during a validated read causes a
  retry.
- **Contention.** An owner committing with `busy_timeout=0` counts its refused commits
  while the viewer refreshes; the test fails if any refusal comes from a validated read.
- **Browserless sessions** under `tests/dom/` drive the production table module through
  sort, filter, paging, opening a record, a live change that adds rows above and below
  the viewport, a removed column, pause and resume, the busy state, an exhausted budget,
  and keyboard movement across cells, with invariants on scroll anchor and focused key.
- **Bounds.** Each constant’s measurement is recorded beside it; a large generated table
  checks that a page in key order or on an indexed column costs an index seek, and that
  an unindexed sort past the threshold is refused rather than run.
- **Paint-exempt rows** only for clamping, sticky positioning, and the flash, each named
  with its evidence in the
  [Parity Registry](../../architecture/arch-parity-registry.md).

## Rollout Plan

Every phase ships in the single artifact.
Phase 2 changes what `.csv` and `.tsv` files open as by default, Phase 3 what `.sqlite`
and SQLite `.db` files open as, and Phase 5 adds a Table tab to JSON and YAML files;
each changelog fragment says so.
The SDK version bump in Phase 1 is a hard gate for installed plugins, as intended.

## Open Questions

- Should a directory of SoftSchema records sharing one contract open as one table, as a
  knowledge base’s folders would?
  The protocol supports it; the open question is the kind rule and the cost of reading
  every file.
- Should a record list be typed by its SoftSchema contract?
  The contract registry is keyed by an envelope a bare list does not have, so this needs
  a rule for naming a list’s contract.
- Should a record list open on its Table view by default?
  That needs a view offered per file rather than per kind.
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
- [Reading Another Application’s SQLite Database](../../../../explorations/sqlite-guest-reads/README.md):
  the measurements and the script that reruns them
- SQLite: [URI filenames](https://sqlite.org/uri.html),
  [WAL](https://sqlite.org/wal.html), [file format](https://sqlite.org/fileformat.html),
  [backup API](https://sqlite.org/backup.html),
  [security](https://sqlite.org/security.html)
- [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md)
- [Plugin System](../../architecture/arch-plugin-system.md),
  [Live Delivery](../../architecture/arch-live-delivery.md),
  [Parity Registry](../../architecture/arch-parity-registry.md)
- [Rendering Large Content](../../../large-content-rendering.md),
  [Design System](../../../design-system.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
