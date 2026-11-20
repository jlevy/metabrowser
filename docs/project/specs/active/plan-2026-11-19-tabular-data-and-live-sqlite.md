# Feature: Tabular Data Browsing and Live SQLite

**Date:** 2026-11-19

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved and in progress.
On 2026-11-20 the owner directed implementation, adopting each Key Decision’s
recommendation as written;
[Decision 12](#decision-12-where-a-record-list-gets-its-table) may be revisited before
Phase 7. Implementation proceeds as a stack of one pull request per phase under epic
`mb-lra6`.

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
  never creates a file beside it, never rolls back another process’s journal, and never
  takes a lock that can refuse the owner’s commit: a rollback-journal database is read
  without a lock, and a read through a live log holds a read mark for one short request,
  updating the log’s shared read marks as every SQLite reader does.
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
  `container = { children = "<route>" }`, naming one of its own plugin’s data-hook
  routes, gets its children as rows in the tree and an address for each child
  (`<file>/<inner>`), on the served folder and on a Git pin
  ([Navigation Containers](../../architecture/arch-plugin-system.md#navigation-containers)).
  Only a kind matched by extension gets the tree’s chevron: the server injects
  `METABROWSER_CONTAINER_EXTS` from extensions alone.
- **Plugins share helpers informally.** A built-in publishes `mb.builtins.<name>` and a
  consumer reads it only at render time, after awaiting the provider kind’s assets.
  Nothing declares the dependency, so nothing checks it.
  Phase 1 replaced this with
  [Declared Dependencies](../../../plugins.md#declared-dependencies).
- **An open file does not refresh.**
  [Live Updates](../../../browsing-files.md#live-updates) says an open file shows new
  content on reopen or reload; only files under `.logs` and `.state` with a few
  extensions auto-reload.
  The page’s one `/api/events` stream carries tree entries only to depth two and catalog
  deltas only for unignored files, so nothing signals a change to an ignored file.
  The stream is one-way and has no connection identity
  ([The Event Route](../../architecture/arch-live-delivery.md#the-event-route)).
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
- **The main file alone is not always consistent.** A checkpoint killed part-way leaves
  some pages new and some old; the log covers the difference.
  Read without its log, such a file failed as `database disk image is malformed`; a copy
  of the file and its log read correctly.
- **`mode=ro` writes beside the database in three states:** it creates `-wal` and `-shm`
  for an idle write-ahead-log database and leaves them, creates `-shm` beside a `-wal`
  that has none, and rewrites a stale `-shm`. In a read-only folder the first two fail.
- **The path matters.** SQLite looks for sidecars beside the resolved file, so a symlink
  in another folder hides them from a stat beside the link, and a second hard link gets
  sidecars of its own: it silently misses the owner’s log, and it reads a killed
  writer’s half-written rows as current, since the hot journal sits beside the other
  name. An owner that exits between the reader’s stat and its open turns a correct
  `mode=ro` into one that creates sidecars.
- **A lock lasts only while its process opens nothing else on the file.** POSIX locks
  belong to a process and a file, so closing any handle on a database or its `-shm`
  drops every lock that process holds there.
  After the reader’s own process opened and closed the main file, an owner committed in
  the middle of the reader’s read; after it opened and closed `-shm`, the owner
  restarted its log under the reader, whose next read failed as malformed.
  The same opens from another process changed nothing.
- **A reader can hold up the owner.** A held read transaction starves the owner’s
  checkpoint until it ends.
  In rollback-journal mode a reader’s shared lock refuses an owner’s commit outright
  when the owner sets no busy timeout, SQLite’s default, and a non-empty journal means
  the owner is inside a transaction at that moment.
  A validated `immutable=1` read takes no lock and refuses nothing, but it succeeds only
  when it is shorter than the gap between commits.
- **A hot `-journal` is a half-written file.** `mode=ro` refuses it with
  `SQLITE_READONLY_ROLLBACK`; `immutable=1` reads the half-written rows.
  `journal_mode=PERSIST` keeps a journal between transactions with its header zeroed,
  which SQLite does not treat as hot.
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
 │ table view (table/)    │ HTTP  │ /api/plugin/table/{schema,rows,record,   │
 │  grid · record         │──────▶│                     card,tables}         │
 │  query state in URL    │       │   └─ [[table_source]]: kind → adapter    │
 │                        │       │        ├─ delimited  (csv, tsv)          │
 │ live: mb.watchFile ◀───┼───────│ /api/events  ├─ records (json, yaml)     │
 └────────────────────────┘  SSE  │  file.changed └─ sqlite ──▶ reader       │
                                  │                            processes     │
                                  └──────────────────────────────────────────┘
```

### The Source Protocol

A source adapter is a Python object the table routes call with a bounded handle on one
file. It answers:

| Method | Returns |
| --- | --- |
| `tables()` | Each table’s `id`, `label`, `group` (`tables`, `views`, `virtual`, `internal`), whether it has a stable row key, and a cheap `estimate` of its rows where the source has one; no counts |
| `schema(table)` | Field descriptors, the key fields, the default columns, outgoing references, and incoming references (other tables’ fields that point here) |
| `rows(table, query)` | One page in the collection envelope, with the table’s count |
| `record(table, key)` | Every field’s value, previewed past the value bound, with references resolved |
| `card(table, key)` | A short summary for a hover card: label, a few fields |
| `generation()` | An opaque token that changes whenever the source’s content may have changed. It only stats files and reads bounded headers, never connects, and runs in the server process: the watch polls it, and every read samples it before connecting, so a change during a read costs one extra refetch, never a lost one |

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
Adapters are synchronous and run on the route threadpool, as sidekicks do today; the
SQLite adapter runs each call in a reader process
([Decision 13](#decision-13-where-sqlite-connections-run)).

**The handle.** An adapter reads through a `ContentRef`, as every hook does, plus an
optional local-path capability: the resolved real path of a file on the served folder.
SQLite needs the path for its sidecars; on a Git pin there is no path, so the blob is
written once to a private folder keyed by its object id, under a size cap, and read
there. A text source needs only the bytes.

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
  `{blob, length, hex}` for bytes; `invalid_utf8: true` marks text that was not valid in
  its encoding, decoded with replacement characters.
  A cut never splits a character: an incomplete trailing sequence is dropped before the
  text is checked.
- `{length, preview: false}` for a value too large to preview where the source cannot
  read part of it, and `{error}` for one the source refused, so one value never fails
  the page.
- `{json, preview}` for a JSON value in a text column the schema calls `json`.
- `{ref: {table, key, label}}` for a reference, resolved for the whole page in one
  batched read.
- `{value, stored}` when a value’s stored type differs from the declared type (SQLite’s
  dynamic typing: text in an `INTEGER` column), so the table shows it rather than
  coercing it.

**Keys and positions.** A record’s `key` is a token the source mints, as `after` is.
Both are stateless and deterministic: the same key value or sort position always encodes
to the same token, under any generation and any server process, so a link holding one
reproduces the view.
A token is bounded by a named constant.
A row with no key (a view’s, a delimited file’s, a record list’s) and a row whose key
would encode past the bound are named by position instead, `@<n>`, together with the
generation it was read under.
In a delimited file or a record list `n` counts in the file’s own order, so it survives
a change of sort or filter; in a view or for an over-long key it counts in the stated
query’s order, and holds only with that query.
When the generation moves, the record refetches the row at that position and, if its
cells differ, says it may now be a different row.
An `after` past the bound is positional in the same way and valid for one generation;
once the generation moves, the next page answers `complete: false` with the reason.

**Query.** One wire shape for every source: `sort`, `order` (`asc` or `desc`), `q`
(search), typed filters `f.<field>=<op>:<value>` (`eq`, `ne`, `lt`, `le`, `gt`, `ge`,
`null`, `notnull`, `contains`), `ref=<table>:<key>` (rows that reference one record),
`cols`, `after`, and `limit`. Sort is one `sortable` field plus the row key as a
tie-breaker in the same direction, so paging is stable.
Search matches text fields only and says which fields it searched.

**Envelope.** The collection convention from the object model draft:
`{rows, next_after, complete, truncated, generation}` plus `columns`, `count`,
`count_complete`, `estimate`, and `skipped`.

- `after` is a cursor naming a position in sort order, not an offset, so one minted
  under one generation stays valid under the next; only the positional cursor above does
  not.
- A count is exact up to a cap and otherwise a lower bound, drawn as “at least
  1,000,000”. `estimate` is a cheap number a source may send beside or instead of a
  count, such as SQLite’s `sqlite_stat1` row count or largest rowid, drawn as
  approximate.
- A filter or search that runs out of budget returns the rows it found in key order with
  `complete: false` and the number of rows it examined; a sort cannot be returned in
  part, so it returns a refusal state naming the field.
- `skipped` counts values a filter or search could not examine, such as values past the
  length limit, drawn as “2 values too large to search”.

**Rows and objects.** Rows are not objects in the object model’s sense: they have no
type, contract, or store entry, and the hover card is the table’s own.
The only shared surface is the collection envelope’s five keys and the arrival rule.

**Bounds.** Every route is bounded by named constants defined beside their code and
listed in [Rendering Large Content](../../../large-content-rendering.md): rows per page,
characters per cell preview, bytes per record value, references resolved per page, a
count cap, the row count past which an unindexed sort is refused, a key token’s length,
and a work budget per request (a wall-clock deadline for every source, plus SQLite
opcodes through a progress handler).
Each value is set from a measurement recorded beside the constant, per the repository’s
[measure-before-bounding rule](../../../../AGENTS.md#browser-and-plugin-boundary).

### Routes, Addresses, and the CLI

The table plugin owns one route set, and every source answers through it:

| Route | Serves |
| --- | --- |
| `GET /api/plugin/table/tables?path=` | The source’s tables with groups and estimates |
| `GET /api/plugin/table/schema?path=` | Field descriptors, keys, references, defaults |
| `GET /api/plugin/table/rows?path=&…query` | One page in the collection envelope |
| `GET /api/plugin/table/record?path=&key=` | One record in full, with back-references counted |
| `GET /api/plugin/table/card?path=&key=` | A hover card |

The kind of the file at `path` selects the adapter, so a new source adds no route.

**A database is a container**
([Decision 9](#decision-9-how-a-database-exposes-its-tables)), under the container
contract as it is built:

- **Children.** The SQLite and fsqlite plugins each declare a `children` data hook, as
  the contract requires a kind’s own plugin to, and each delegates to its adapter’s
  `tables()`. It returns `{children: [{name, path}]}` with names only; counts arrive
  with a table’s rows.
  A watch on the database refreshes its children, since an owner can create a table at
  any time.
- **Addresses.** `app.db` is the database’s overview, which lists its tables and views
  as links with their estimates, so navigation never depends on the tree.
  `app.db/<segment>` is one table, an address that works on a Git pin as every
  container’s does. The segment is the table’s name when the name is nonempty, is not `.`
  or `..`, does not start with `~`, and holds only characters a path segment keeps as
  they are; any other name is `~` followed by the hexadecimal of its UTF-8 bytes, so
  every name SQLite allows has exactly one segment.
- **The chevron.** The tree draws a chevron from the kind’s extensions, as it does for
  every container. Two costs follow, and the plan accepts both: a `.db` file that is not
  SQLite shows a chevron that expands to nothing (its `children` hook answers an empty
  list, not an error), and a database with no extension, such as a browser’s `History`,
  has no chevron and is reached by opening it.

A single-table source (a CSV file, a record list) is its own table.
Sort, filters, search, columns, and the open record (`record=<key>`) are query state on
the table’s address, the same for every source; a record is not a path segment, since
its key is an opaque token.
`metab --show app.db/users` and the `--api` goldens name tables by the same addresses.

### Framework Improvements

**Declared plugin dependencies.** `[plugin] requires = ["table"]` in a manifest.
The loader refuses a missing or cyclic dependency, and `metab --doctor` reports the
graph. In the browser, `await mb.plugins.load("table")` returns the provider’s exports
(its `index.js` module’s) after its assets have run, replacing the render-time-only
`mb.builtins` convention.
Markdown, structured data, agent logs, the folder README panel, and the pull request
page move to it in the same change, and the rule and its test change with them.
As built, a provider loads on demand when a dependent asks for it, not before the
dependent: every existing consumer needs its provider only on some pages (a folder with
a README, a pull request with a diagram), and loading Markdown with every folder would
put its module graph on the start page.

**Binary kinds by magic number.** A `[[kind]]` match may name `magic` (an offset and the
bytes expected there).
Every file that would otherwise be `binary` is checked against every magic rule,
whatever its extension, so a database named `History` or `x.storedata` opens as one; a
magic kind’s `exts` decide only the chevron.
Every classification site checks it: `api_file` after images and before the binary
fallback, reading only the sniff prefix it already reads; `classify_identity` for a Git
blob, from the prefix the caller already holds; `_resolve_container_child`; and
`metab --show`. The SQLite kind matches `SQLite format 3\0` at offset 0 with extensions
`.sqlite`, `.sqlite3`, `.db`, `.db3`, and `.s3db`; a `.db` file that is not SQLite stays
binary. Magic is checked on the bytes on disk, so a compressed database (`x.sqlite.gz`)
stays binary.
These reads happen in the server process, which is why no SQLite connection
to such a file runs there ([Decision 13](#decision-13-where-sqlite-connections-run)).
The file-type registry moves `db` from `configuration` to the `sqlite` kind and adds the
other extensions, with a revision bump.
This also lets a future installed plugin claim LMDB or Parquet without a core change.

**File watches on the event stream**
([Decision 4](#decision-4-how-an-open-file-learns-it-changed)).
`mb.watchFile(path, {onChange})` registers a path for the page’s existing `/api/events`
connection and returns a disposer:

- The stream’s `fs.snapshot` frame carries a connection id.
- `POST /api/events/watch` with `{connection, path, generation}` registers the path and
  answers with its current generation, so a change between the page’s fetch and its
  registration is seen at once.
  The same route with `watch: false` unregisters it, so both reach `metab --api`.
- The server polls the registered paths the inventory does not already deliver (ignored
  or deeper than the stream’s scope) on a bounded interval, through the kind’s source
  `generation()`, or identity, size, and modification time for any other file, and sends
  one `file.changed` event with the new generation, coalescing bursts.
  Registered paths per connection are bounded by a named constant, set from a
  measurement of the polling cost.
- The shell’s page-connections owner (`shell.page-connections`) keeps the watches, so a
  page still holds one stream, and re-registers each with the generation it holds after
  a reconnect, an `fs.resync_required`, or a server restart, which answers an unknown
  connection id with a refusal.
- On a Git pin the route answers `unsupported_for_subject`, as `/api/events` does; a
  pinned file cannot change, so there is nothing to watch.
- Parity: the route is a JSON route with goldens for registering and unregistering under
  an unknown connection, each refused, and the page-connections browserless session
  covers registration and re-registration.

`/api/stream` stays the JSONL log tail; the two do not interact.

### The SQLite Source

**Shared access helper.** `src/metabrowser/sqlite_access.py` holds the one way the
product opens a database it does not own: header admission, the access choice below,
connection settings, the work budget, and error classification.
The GitHub catalog moves onto its admission and settings in the same change, and its own
opens (`_admit`, `_database`) are checked then against the lock hazard below.

**Reader processes** ([Decision 13](#decision-13-where-sqlite-connections-run)). Every
connection to a database the product does not own runs in a reader process from a pool
whose size and queue are named constants, never in the server process.

- **Start.** A worker is a fresh interpreter (`spawn`, never `fork`, which copies a
  threaded server and its open connections) importing only `sqlite_access` and the
  adapter, on macOS and Linux, as the repository cache is.
- **Work.** One adapter call at a time, its request and answer bounded by the page and
  preview bounds. A worker opens and closes a database’s files only outside a connection,
  so nothing in its own process drops its locks.
- **Deadlines.** A request’s deadline counts from when it is queued; at it a watchdog
  thread in the worker calls `Connection.interrupt()`, since `count(*)` runs a handful
  of opcodes and never reaches the progress handler.
  At the later hard deadline the parent kills the worker.
  A full queue or a kill answers the busy state, which keeps the last good rows.
- **Lifecycle.** The parent creates and removes every private folder and sweeps
  leftovers at start. A worker exits when its pipe closes; one that is killed or crashes
  is replaced, and a crash answers the reader-stopped state with no automatic retry.
  Under the untrusted profile a worker serves one subject.
  A one-shot `metab --api` or `--show` starts one worker, so goldens run the same path.

**Choosing how to open.** The worker resolves the path’s real file, stats it and its
sidecars beside that file, and reads the 100-byte header, then decides before SQLite
touches anything:

| Header and sidecars at the real path | Open | Shown as |
| --- | --- | --- |
| Any journal mode, more than one hard link | As a missing `-shm` below, through a private copy | **Another name**, never Current: “this file has N names; a journal or log kept beside another name is not shown” |
| Rollback journal | `immutable=1`, validated, never locked ([Decision 10](#decision-10-reading-a-rollback-journal-database)) | Current, or **writer busy** |
| Write-ahead log, no `-wal` or a zero-byte one | `immutable=1`, validated | Current |
| Write-ahead log, `-wal` with frames, `-shm` present | `mode=ro`, with the race check | Current |
| Write-ahead log, `-wal` with frames, no `-shm` | Under the copy cap, a private copy of the main file and its `-wal`, validated, read `mode=ro`; past the cap, or after a copy fails validation twice, the main file with `immutable=1` | Current; past the cap, “without its N-byte log, which may be inconsistent” |
| Immutable content: a Git revision, an fsqlite snapshot | `immutable=1` | Current; a committed write-ahead-log database is shown without its log |

- **A live journal** holds bytes and a header that is not zeroed;
  `journal_mode=PERSIST`’s idle journal and a zero-byte one count as none.
- **Validated** means no live journal or log frames appeared, and the main file’s
  identity, size, modification time, and header change counter, and the `-wal` file’s
  size, modification time, and header, match before and after the read.
  A write-ahead-log checkpoint leaves the change counter as it was, so a file modified
  within a named timestamp granularity of the first stat counts as changing, as Git
  treats a racy index entry.
  A **private copy**, in a private folder, takes the main file before its `-wal`, so a
  checkpoint during the copy moves only pages the log still holds, and is validated the
  same way across the copy.
- **Waiting out.** A live journal or a failed validation is retried with backoff, each
  retry re-running the choice from the top, until the request’s deadline; then a
  rollback-journal database is writer busy and any other is changing.
  An error from a read that failed validation is changing, never damaged, and in the
  another-name and past-the-cap states a corruption error is that state, not damage.
- **The race check.** Before connecting, the worker opens the `-shm` it saw, read-only,
  and holds it until after the connection closes; after connecting, it compares that
  file’s identity with the path’s, as `pull_catalog._database` already does for the main
  file. If the owner exited in between and the open created sidecars, the Info view says
  so.

**Every request is short:** it samples the generation, opens a fresh connection, reads
in one short transaction, and closes it.

- **Counts** run as `SELECT count(*) FROM (SELECT 1 FROM t LIMIT :cap + 1)`, which the
  budget can stop and which yields “at least cap” directly.
  A count runs only with a table’s rows, validated apart from the page as one further
  read with no wait; when that fails, the envelope sends `estimate`.
- **Paging** is keyset by the sort value and the row key, ascending or descending.
  It is an index seek only in key order (the rowid or primary key) or on a column that
  leads an index; past the measured row count, `schema()` marks every other field
  unsortable and says why.
  Nulls sort first ascending and last descending, and a row-value comparison with null
  is unknown, so a sorted column pages its null rows by key (`s IS NULL AND id > ?`) and
  the rest by row value (`(s, id) > (?, ?)`), each by its own seek and mirrored
  descending; the cursor names its region and continues into the next, since one
  predicate spanning both is a scan.
- **Filters and search** are scans by nature and return partial results under the budget
  as the envelope describes.

**Values.** `SQLITE_LIMIT_LENGTH` fails a whole statement, not one cell, so every
expression over a value is guarded by its size.
A select reads `CASE WHEN octet_length(v) <= :limit THEN v END` with `octet_length` and
`typeof` beside it; a filter or search adds `octet_length(v) <= :limit` and counts what
it skipped; a sort that fails on a value past the limit is refused with a `sort_note`. A
value over the measured preview threshold is previewed through `Connection.blobopen`,
which reads part of a text or blob in a rowid table; in a `WITHOUT ROWID` table or a
view, where `blobopen` is unavailable, the cell shows the size alone.
`blobopen` returns the stored bytes, so previews are decoded by the database’s
`PRAGMA encoding`, which may be UTF-16. `octet_length` needs SQLite 3.43, the reader’s
minimum: under an older library a database opens to its Info view, which says so.
The record route applies the same rules.

**Connection settings,** each a named constant: `query_only`, `trusted_schema=OFF`,
`SQLITE_DBCONFIG_DEFENSIVE`, `cell_size_check=ON`, `mmap_size=0`, a small cache, a short
busy timeout, limits on value length, SQL length, columns, expression depth, and
attached databases, and an authorizer.
The authorizer allows `SELECT` and reads; functions in the adapter’s own SQL from an
allowlist; any function called inside a view, which its last argument names, since the
server registers no functions of its own and `trusted_schema=OFF` refuses there every
built-in not marked innocuous; and the pragmas the adapter uses.
It denies everything else, `ATTACH` included.
Extension loading stays off.

**What it shows.**

- **Tables:** tables, views, and virtual tables in their own groups, and internal tables
  (`sqlite_sequence`, `sqlite_stat*`, virtual tables’ shadow tables, and, for an fsqlite
  snapshot, `fsqlite_meta` and `applied_tx`) under `internal`, each with an estimate.
  A virtual table is never queried under the untrusted profile, and elsewhere only when
  the library is at or past the minimum the code names.
- **Columns** come from `table_xinfo`, so hidden and generated columns show; a `STRICT`
  table is marked; a table whose own columns shadow `rowid` keys by another alias or by
  its primary key.
- **Keys:** the rowid, or the primary key of a `WITHOUT ROWID` table.
  A view has no key, so it pages by position and its rows are named by position.
- **Types:** the declared type and the affinity it implies, and the stored type when a
  value differs.
- **References:** declared foreign keys become `ref` fields and back-references; a
  reference to a missing row is drawn as missing.
- **Schema view:** each object’s DDL, indexes, triggers, and foreign keys.
- **Info view,** from pragmas on the connection, since the main file’s header is stale
  while a log holds frames: page size and count, encoding, journal mode, `user_version`,
  `application_id` (named when known, such as fsqlite’s `FSQL`), freelist size, the
  sidecars and the log’s size, the access mode chosen and why, and the SQLite library
  version against a table in code of versions and what each means for a reader, the
  reader’s minimum among them.

**Generation,** from stats and headers alone: the main file’s identity, size,
modification time, and change counter, plus in write-ahead-log mode the `-wal` file’s
size, modification time, and header checkpoint sequence and salts (bytes 12 to 24),
which change every time the log restarts even when its size repeats.

**fsqlite stores.** The store’s `fsqlite.json` is the `sqlite-store` kind:
`folder_marker = "fsqlite.json"` with `json_has_key = "format"` and
`json_value_prefix = "fsqlite"`, so the folder gets its badge and opening the marker
opens the store, with no core change.
It reads the snapshot `current` names, `immutable=1`, retrying when garbage collection
removes it between the two reads, and shows the generation number, which `current` gives
its `generation()`. Pending transaction envelopes are counted in its Info view.
It is a thin source over the SQLite adapter and a container like any database, with its
own `children` hook.

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
- Rows have no key; a row is named by its position.
- The generation is the file’s identity, size, and modification time.
- A file under the parse cap is held in a per-generation cache, bounded in bytes and
  entries, with a sort index built on demand.
  A larger file shows its leading rows; its sort, filter, and count say they cover only
  those rows (`complete: false`).

Views: Table (`v`, the default) and Source (`s`).

**Record lists** are a Table view (`r`) of the structured plugin’s `structured` kind,
beside Tree and Source, reading the `parsed` hook’s result under its existing bound
([Decision 12](#decision-12-where-a-record-list-gets-its-table)). The Table tab draws a
top-level list of mappings and, for any other document, says it is not a list of
records; Tree stays the default.
Fields are inferred from the records, rows are named by position, and the generation is
the file’s, as for delimited text.
Nested mappings and lists are `json` cells, drawn in the record with the structured
plugin’s inline tree.

### The Table View

**Layout.** The grid fills the view, and the record opens in place of the grid with a
Back path, as paraverse’s does.
A database’s tables are its children in the tree and links on its overview, not a second
list inside a table’s view.
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
- Sorting from the header of a sortable column, in either direction; a search box;
  per-column filters from the header menu; every active filter as a removable chip.
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
A record named by position says so.

**Live behavior.** On `file.changed`, the view refetches the current window with the
same query, coalescing bursts within one bounded window as `createInventoryWatch` does.

- It keeps the scroll anchor, the focused row by key (by position in a keyless table),
  open menus, and unsent filter text.
- Rows whose cells changed flash once in `--row-flash-bg`, following
  [Live Row Arrivals](../../../design-system.md#live-row-arrivals) and its
  reduced-motion treatment.
- New rows that would land above the viewport are offered (“3 new rows”), not inserted
  under the reader, following the arrival rule.
- A column or table that disappeared is dropped from the URL state with a notice.
- An open record named by position is refetched and, if the row at that position
  changed, says it may now be a different row.
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
That parser runs only in reader processes, never in the server.
A reader process isolates a crash and allows a hard stop, but it is not a sandbox: it
has the server’s privileges.
An address-space limit set in the worker (`resource.setrlimit`, a named constant) bounds
a crafted file’s memory where the platform enforces one.
The connection settings above are the defense: `trusted_schema=OFF` refuses functions
and virtual tables not marked innocuous inside views and triggers, `DEFENSIVE` and
`cell_size_check` guard against a corrupt file, the authorizer admits only reads, a read
fires no triggers, and the budget, deadline, and kill stop an expensive view or
recursive query. Virtual tables are listed but never queried under the untrusted profile
(repository mirrors), where immutable content is read through `immutable=1`. Text is
rendered as text, never as HTML.

The SQLite access phase gets two dedicated reviews: a security review, and a correctness
review of `sqlite_access.py` and the reader processes against the access table and the
lock hazard. The table routes and the watch get a performance review.

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
- **C. File watches registered on the page’s existing `/api/events` connection,**
  through a registration route keyed by a connection id the stream sends.
- **D. Watched paths in the stream’s own query,** reopening the stream when they change.

**Recommendation: C.** The server speaks HTTP/1.1, so a browser shares six connections
per origin across every tab; before the page-connections owner, the sixth page waited 55
to 56 seconds for one ([Parity Registry](../../architecture/arch-parity-registry.md),
`shell.page-connections-browser`). A puts a second standing stream on every page that
shows a table. B misses ignored files and paths deeper than its scope.
D pays a full snapshot each time a page opens or closes a watch.
C adds one event, one route, and a bounded registration to the stream the page already
holds, and the registration’s answer closes the window between a fetch and the watch.

### Decision 5: A Write-Ahead-Log Database With No Frames in Its Log

- **A. A validated `immutable=1` read.**
- **B. `mode=ro`, accepting the sidecars it creates.**

**Recommendation: A.** B leaves `-wal` and `-shm` beside someone else’s database and
fails in a read-only folder.
A is valid only while the log is absent or empty before and after the read; a log with
frames is read with `mode=ro` through its wal-index, or through a private copy when that
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
The private copy in the access table covers the one sync-folder state the reader can
detect, a log with no `-shm`.

### Decision 9: How a Database Exposes Its Tables

- **A. The database kind is a navigation container** whose children are its tables and
  views.
- **B. A list of tables inside the view,** with the table in view URL state.

**Recommendation: A.** The container contract already gives a file children in the tree,
an address per child, views that receive `container_inner`, and Git-pin support.
B would duplicate the tree, give a table no address of its own, and leave `metab --show`
nothing to name a table by.
A fits the contract unchanged: each source plugin declares its own `children` hook, the
chevron follows the kind’s extensions, and the overview’s table links reach the tables a
chevron cannot, at the two costs
[Routes, Addresses, and the CLI](#routes-addresses-and-the-cli) states.
Making the chevron follow content instead would read every candidate file on every
inventory pass.

### Decision 10: Reading a Rollback-Journal Database

- **A. Never lock:** a validated `immutable=1` read of the page, waiting out a live
  journal or a failed validation until the request’s deadline and then answering writer
  busy; the count validated apart with no wait, else `estimate`.
- **B. Lock-free first, then lock:** as A, but past the wait a locked read of the
  key-ordered page alone.
- **C. `mode=ro` always,** with each read’s lock bounded by the deadline.

**Recommendation: A.** A reader’s shared lock refuses an owner’s commit when the owner
sets no busy timeout, and live refresh reads exactly when the owner is writing.
In the
[contention record](../../../../explorations/sqlite-guest-reads/README.md#contention) A
refused no commit at any pace, by construction, and its key-ordered page was valid on
every read, even against a back-to-back writer.
B locked on most reads at 5 ms, since validating the page with its count fails whenever
the count outlasts the gap between commits, and its locked page ignores the request’s
sort, filter, and cursor.
A’s cost: a first open during a long owner transaction shows writer busy with no rows,
where B would show the key-ordered page; a hot journal is refused either way.
The contention test asserts that no commit is refused.

### Decision 11: Windowing the Grid

- **A. The table owns a fixed-row-height grid window now,** with a tracked follow-up to
  converge with the object model’s list host once that lands.
- **B. Wait for the list host.**

**Recommendation: A.** The list host is an unapproved draft that draws variable-height
rows, not a column grid, and B would hold the owner’s main goal behind it.

### Decision 12: Where a Record List Gets Its Table

Views bind to a kind, and nothing offers a view per file.

- **A. A Table view on every `structured` file,** beside Tree and Source, which says
  “not a list of records” for any other document.
  It needs no new kind, predicate, or framework surface; its cost is a Table tab on
  every `package.json` and configuration file.
- **B. A view-availability hook:** a view declares a check the shell asks per file, here
  whether the parsed top level is a list of mappings, so the tab appears only on record
  lists and could be their default.
  It is a new framework surface, and it adds a check to every structured file’s open.
- **C. Defer record lists** until a consumer needs them.

**Recommendation: A** for this plan, with B as the follow-on if the tab on other files
proves to be noise. A dedicated kind is not an option: its list predicate, under the
classifier’s byte bounds, would miss exactly the large files that most need a table.

### Decision 13: Where SQLite Connections Run

- **A. A small pool of reader processes,** each serving one request at a time, which
  open a database’s files only outside a connection’s lifetime.
- **B. The server process, trusting no lock:** identity and size from `os.stat`, which
  opens nothing; every `mode=ro` read validated as the lock-free reads are; an error
  from a read that failed validation shown as changing; and no handle on the main file
  or `-shm` held by the access helper.

**Recommendation: A.** A lock belongs to a process and a file, and the server process
opens these files for reasons of its own: the magic check, header reads, inventory
sniffing, hashing. Only A keeps any of those from dropping a reader’s locks, without a
rule every future code path must follow.
B can detect a broken read but not prevent one, so against a busy owner its locking
reads keep failing validation.
A also gives a hard deadline, by killing the worker, and keeps SQLite’s parser for
untrusted files out of the server.
The [process record](../../../../explorations/sqlite-guest-reads/README.md#process)
shows the race check’s held handle keeping the reader’s locks, a killed reader leaving
the owner nothing to clean up, and the cost: a spawned worker answers first in tens of
milliseconds, and a warm page’s round trip costs about three times the read in process.

## Implementation Plan

Eight phases, each one stack and each accepted on its own, so live SQLite does not wait
on everything else. Each source brings its generation token in the phase that adds it.

### Phase 1: Declared Plugin Dependencies

- [x] Manifest `requires`, loader validation (load order left as discovered, by design:
  a dependent loads its provider on demand), `mb.plugins.load`, doctor report; move
  every `mb.builtins` consumer; update [Plugin Authoring](../../../plugins.md) and
  [Plugin System](../../architecture/arch-plugin-system.md)
- [x] `PLUGIN_SDK_VERSION` bump with every built-in manifest updated

### Phase 2: The Table Protocol and Delimited Text

Accepted from the CLI, before any browser view.

- [x] Source protocol types and wire contract in core; `[[table_source]]` declarations
- [x] The five routes, the envelope, keys and positions, bounds measured and recorded
- [x] Delimited source and kind, with its generation; the kind keeps Source as its only
  view until Phase 3
- [x] Parity rows, `--show` and `--api` goldens, the map in
  [Views, Models, and Routes](../../architecture/arch-views-models-routes.md), changelog
  fragment

As built, where this plan left a choice open:

- A position counts from 1, the first row after a delimited file’s header, and a blank
  line is not a row. An empty value is null in a column of any type but text.
- A source that is its own single table names it `""`, addressed by the file’s own path;
  a path naming a table inside a file waits for the first multi-table source (Phase 5),
  as do the segment escape, the count cap, the unindexed-sort threshold, references
  resolved per page, and the opcode budget, which only SQLite needs.
- A record request may name the `generation` its key was read under, and the answer’s
  `generation_moved` says whether the content changed since; comparing the cells is the
  view’s.
- A keyless row breaks sort ties by its position, so a row inserted above it in the file
  moves it, and a cursor continues from the sort position it names.
- `requires = ["table"]` is declared because the table plugin’s routes serve the source;
  a manifest with a `[[table_source]]` that does not require `table` is refused.
- The envelope also carries `reason` (why a page is not complete: `budget`,
  `sort_budget`, `source_truncated`, or `cursor_expired`), `examined` (the rows a scan
  reached before its budget ran out), `searched` (the fields a search read),
  `sort_refused`, and `limit` (the rows the page allowed).
- A filter or search that runs out of budget answers the rows it found in the query’s
  own order, and its cursor continues among them; a sort the budget cannot finish,
  whether in the scan before it or in building its index, answers no rows with the
  reason `sort_budget` and the field in `sort_refused`, as above.
- `cols` names one field per parameter and repeats (`cols=a&cols=b`), since a delimited
  header may hold a comma; `ref` splits at its last colon.
- A page carries at most `TABLE_PAGE_CELLS_MAX` cells, so a page of wide rows has fewer
  rows than its `limit` asked for.
  A delimited file is bounded in rows, cells, and columns as well as bytes, since its
  costs follow those.
- A `c.` cursor names the sort field and order it was made for, and a cursor for another
  is refused.
- Of the cell envelopes above, this phase builds the integer, real, text (with `length`
  and `invalid_utf8`), and `{value, stored}` ones.
  `{blob, length, hex}`, `{length, preview: false}`, `{error}`, and `{ref}` arrive with
  SQLite tables (Phase 5), and `{json, preview}` with the first source that types a
  field `json` (Phase 5 or 7); a table view meets only the built ones until then.

### Phase 3: The Table View

- [x] The table view: grid, windowing, filters, search, sort in both directions, column
  fit, record view, hover cards, URL state, keyboard, accessibility; Table becomes the
  delimited kind’s default
- [x] Data Tables section in the design system; folder tables adopt it; `.data-table`
  deleted
- [x] The browserless table session, parity rows, changelog fragment

As built, where this plan left a choice open:

- **Fixed row height, one or two lines.** A table’s rows are one line, or two when a
  value it reads first is cut or longer than its column; every row of a table is that
  one height, whole or windowed, so the window places a row by its index.
  A column’s width comes from its header and the first values that showed it, in the
  face they are drawn in, and holds for the table’s life.
- **Whole or windowed** is decided by the first answer’s exact count against
  `WHOLE_TABLE_MAX_ROWS`, measured in Chrome (`tests/dom/table-view-measure.mjs`); a
  windowed grid reads the next page as the window nears the last row held, so its scroll
  height grows with what it has read rather than standing for the count.
- **One filter per field in the view.** The header menu and the value links keep one
  filter per field, and a new one replaces it; the route takes more, and a range waits
  for a reader who needs it.
- **Repeated parameters.** `fetchPluginData` sends an array value as its parameter
  repeated, one value each, so `cols` names one field a parameter in the request and in
  the address alike, and a field whose name holds a comma is one column.
- **Pages the server bounds.** The view asks for `FIRST_PAGE_ROWS` and then
  `NEXT_PAGE_ROWS`, and counts the rows that came: a page of wide rows carries fewer
  (its `limit` says how many), so a table small enough to draw whole is read until its
  `next_after` ends, and a window reads its next page as soon as the last is drawn.
  A cursor continues only the question it was made for; while a new question’s first
  page is on its way, the rows held for the last read no further.
- **What a budget did.** A sort refused with `sort_budget` is a notice naming the field,
  with a link to the file’s order, not an empty table; a search stopped with `budget`
  shows the matches among the rows it read and says how many it read, and scrolling
  reads on among them.
  A page that says `truncated` with an exact count was cut in a row’s cells, and one
  with a lower bound in its rows, and the notice says which.
  `tests/test_table_view_session.py` records these answers with each bound lowered for
  one small file, since a file that meets the real bound is too large to record.
- **The open record** is `record=<key>` on the table’s address, which the view reads and
  the rows route ignores; a record opens in place of the grid, and Back, or its own Back
  link, returns the grid with the keyboard on the row.
  The scroll position and focused row are kept in the history entry’s state, not the
  address.
- **Hover cards** are the shared tooltip’s content, shown on hover and on keyboard focus
  of a reference chip, and nothing in a card is interactive, since a tooltip takes no
  interactive children; the chip itself opens the record.
  Delimited text has no references, so the card waits for SQLite (Phase 5) to be
  exercised against a source; the session checks how a reference cell is presented.
- **JSON and blob values** are shown as text in the record until a source sends them
  (Phases 5 and 7), which can then draw them through the structured tree and the binary
  view.
- **Address changes** reach the view through `navigation.open` and the window’s
  `popstate`, which the shell’s controller applies first; `navigation.open`’s `replace`
  option, which the shell already took, is now documented.
- **Warming the provider** (review A9 of Phase 1): the delimited plugin starts
  `mb.plugins.load("table")` when its own module is evaluated, since its kind always
  opens in the Table view; starting every declared provider with its dependent would put
  Markdown on every folder’s page.
- **Select all in a windowed grid** is Home and then Shift-End, not Command-A: every
  page key handler leaves a chord to the browser (`tests/test_modified_keys.py`), so
  Command-A keeps the browser’s own select all, which in a window holds only the rows
  drawn.
- `.table-container`, unused like `.data-table`, went with it; the folder tables take
  `.data-num` and `.data-label`.

### Phase 4: SQLite Access

Accepted from `metab` through the Info view, before any table is drawn.

- [ ] `magic` kind matching at every classification site; file-type registry move and
  revision
- [ ] Reader processes; `sqlite_access.py`: admission, the access table, private copies,
  Git blobs written once under a cap, the race check, connection settings, authorizer,
  budget, deadlines, and kill, error states; the GitHub catalog moved onto it
- [ ] The Info view
- [ ] Nondestructive access, lock hazard, and contention tests, goldens, parity rows,
  changelog fragment; dedicated security and correctness reviews

### Phase 5: SQLite Tables

- [x] SQLite source as a container with its `children` hook and overview: tables, keys,
  typed cells, references and back-references, keyset paging in both directions,
  sortability, capped counts, size-guarded values, the generation
- [x] Schema view, goldens, parity rows, map updates, changelog fragment

As built, where this plan left a choice open:

- **The SQL runs in the reader.** `builtin_plugins/sqlite/reader.py` is a worker module
  (`register_worker_module`) holding every statement; `source.py` in the server turns
  what it answers into descriptors, cells, keys, and cursors with the protocol’s
  helpers, so a value crosses the pipe in a small encoding of its own (`_wire`) and
  every token and cell rule stays in `table_source.py`.
- **A table’s id is its address segment**, the escaped name, so a reference, a `ref=`
  filter, and the view’s sibling addresses need no mapping; its label is the name.
  A name starting with `g1-`, a Git path segment’s prefix, is escaped too.
- **`open_table_source` resolves `<file>/<table>`** through
  `resolve_content_container(path, suffixes=None)`, which now claims any extension, so a
  database with no extension has addressable tables; every route but `tables` answers at
  the table’s address.
  Every `sqlite` route takes a table’s address and answers for its database.
- **One Table view, two pages.** The `sqlite` kind’s Table view is the overview at the
  database’s address and `mountTable` at a table’s, since a container’s children share
  its kind and views; Table is the default, and Info keeps its key.
- **Keys.** A rowid table without an integer primary key is keyed by a hidden `rowid`
  field (`_rowid_` or `oid` when a column takes the name); a table whose columns take
  all three is keyless.
  A key too long for a token is named by its position in key order, found by a count; a
  cursor too long is the positional one, carrying the rows served.
  A keyless object is ordered by `row_number() OVER ()` whenever a page sorts, filters,
  searches, or reads descending, and read by `OFFSET` otherwise.
- **Cursors** are `[sort, order, region, value, key, served]`; every row knows its
  region from its sort value’s type, so a positional cursor continues into the right
  one.
- **Sortability** is decided per object by a capped count up to
  `SORT_UNINDEXED_MAX_ROWS` at describe time; past it the key, the first column of a
  `WITHOUT ROWID` key, and every column that leads a full (not partial) index sort.
- **Counts** read as `sum` over at most `COUNT_CAP` + 1 rows: with a filter or search it
  counts matches and skipped values among the rows read, so a sparse filter on a huge
  table is a lower bound rather than a scan.
  A match in a select list is a `CASE WHEN` condition, since only a condition
  short-circuits past a value over the length limit.
- **Values.** A text read only in part is `{text, bytes}`, its size in bytes, since its
  length in characters is unknown; a blob is `{blob: true, length, hex}` (`blob_cell`).
  A JSON column’s text is `{json, preview}` only when it parses and fits the preview.
  A `BOOLEAN` value other than 0 or 1 is shown as stored, and an order filter (`lt`,
  `le`, `gt`, `ge`) compares only values of its own kind, since SQLite orders every text
  after every number.
- **References** are resolved in SQL, joining the page’s values to the target table, so
  the target column’s affinity and collation decide a match; a missing target is
  `{ref: {key: null, missing: true}}`, which the table view draws as its value marked
  missing. A reference’s label is the referencing value.
- **The authorizer** also admits `data_version`, which FTS5 reads on every query, and
  the functions `sum`, `substr`, `like`, and `row_number`. Virtual tables are read where
  the folder is trusted and never on a pin.

### Phase 6: Live Tables

- [ ] File watches on `/api/events`: connection id, the registration route,
  `file.changed`, `mb.watchFile`, bounded paths, re-registration under
  `shell.page-connections`
- [ ] The table’s live behavior; container children refreshed on change; performance
  review

### Phase 7: Record Lists

- [ ] The Table view of the `structured` kind as Decision 12 settles it, with its
  generation, goldens, and parity

### Phase 8: fsqlite Stores

- [x] The `sqlite-store` kind, its `children` hook, snapshot reads, generation, goldens
- [x] Its tables through the SQLite source over the snapshot, its Table and Schema
  views, goldens, parity rows, map updates, changelog fragment

As built, where this plan left a choice open:

- **Recognition** is the marker alone, as the fsqlite specification requires (M2): a
  folder holding `current` and `snapshots/` without `fsqlite.json` is a folder.
  The marker is parsed strictly once the kind is chosen: malformed or naming another
  format is `invalid`, and a format version or required feature this reader does not
  know (`SUPPORTED_FORMAT_VERSIONS`, `SUPPORTED_FEATURES` in
  `builtin_plugins/fsqlite/store.py`) is `unsupported`, never `corrupt`.
- **The pointer and the snapshot.** A pointer that is not trimmed ASCII digits within
  its bounds, is missing, or names a snapshot missing at both of two reads is `corrupt`;
  a snapshot whose `application_id` is not fsqlite’s is `corrupt` and still shown.
  The snapshot read through the reader pool goes back to the pointer when the reader
  finds the file gone (`unreadable` with nothing at the path), as when the lookup does.
- **Generation** is `<version>-<hash>`: the version, so a reader sees which head a table
  shows, and a hash of the identity, size, and time of `fsqlite.json` and `current`.
  Pending envelopes change no snapshot and are not in it.
- **Pending envelopes** are counted as committed (holding `COMMITTED`) and uncommitted,
  by one stat each, and the scan stops at `PENDING_SCAN_MAX` entries.
- **The Info view** is the store’s section above the snapshot’s, drawn with the SQLite
  plugin’s model and drawing, which that plugin now exports to a plugin that requires
  it.
- **On a Git pin** the store’s routes answer `unsupported_for_subject`: its files are
  resolved beside the marker by path, which a pin’s identities do not offer a hook.
- **Tables.** The store’s `[[table_source]]` (`builtin_plugins/fsqlite/source.py`) is
  Phase 5’s `SqliteSource` with an opener: the database is the snapshot `current` names,
  read with `immutable_content` under the store’s generation, and its `tables()` pass
  through `group_reserved`, which groups `applied_tx` and `fsqlite_meta` as internal.
  The SQLite reader already groups them so in any snapshot carrying fsqlite’s
  `application_id`, so a snapshot opened by itself as the `sqlite` kind shows them
  internal too, and `group_reserved` keeps them so in a store whose snapshot lacks it.
  A table is `<marker>/<segment>` with the SQLite plugin’s segment escaping; the
  `table/*` routes reach it as `<file>/<table>`, since the marker is the file.
- **One open, every route.** The children and schema hooks and the table source each
  open the snapshot through `open_store`, which reads the snapshot’s catalog inside the
  pointer retry, so a snapshot garbage collection removed before a reader opened it
  sends every route back to the pointer once.
  A later read in the same request that finds it gone answers as the reader refused it.
  An `invalid`, `unsupported`, or `corrupt` store is `source_unreadable` (422) on the
  table routes, naming its state.
- **Views.** The kind’s views are the `sqlite` kind’s, Table (the default) and Schema,
  then Info, drawn by the SQLite plugin’s `mountTableView` and `mountSchema`, which it
  now exports; Schema reads `fsqlite/schema`, which answers as `sqlite/schema` does, and
  Info and Schema answer at a table’s address for its store.

## Testing Strategy

- **Goldens.** Each source has `--api` goldens over every table route and a `--show`
  golden for its kind and for a table’s address.
  SQLite fixtures are built in each golden’s `before:` script from reviewable SQL text,
  not committed binaries, and cover rowid, `WITHOUT ROWID`, views (one calling built-in
  functions), virtual tables, composite and blob primary keys, composite foreign keys,
  nulls in a sorted column in both directions, mixed stored types, integers past 2⁵³,
  infinite reals, invalid UTF-8 text, a UTF-16 database, blobs, long text, a value past
  the length limit, JSON text, hidden and generated columns, a `STRICT` table, table
  names that need the escaped segment, a database with no extension and one with an
  unlisted extension, and an fsqlite-marked database.
- **Nondestructive access tests**, grown from the
  [exploration’s cases](../../../../explorations/sqlite-guest-reads/README.md#access),
  each with a real owner in a second process and a directory listing before and after:
  an idle write-ahead-log database creates nothing; a read-only folder reads; a crashed
  owner’s `-wal` with and without `-shm`, writable and read-only, reads; a checkpoint
  killed part-way reads through its log; an owner’s new table not yet checkpointed
  shows; an owner that exits between the stat and the open is reported; a symlink in
  another folder reads the right state; a second hard link, to a write-ahead-log
  database, to one with a hot journal, and to one whose checkpoint was killed, is shown
  as another name, never as current or damaged; a hot journal yields the busy state and
  leaves the journal untouched; a reader’s requests never stop a
  `wal_checkpoint(TRUNCATE)`; a commit changes the generation, and one that lands during
  a `mode=ro` read is followed by a `file.changed`; an owner starting during a validated
  read causes a retry.
- **The lock hazard.** A `mode=ro` read in a reader process, while the server process
  opens and closes the database and its `-shm` and the owner commits and checkpoints:
  the owner stays refused and the read stays intact.
  A worker killed inside a read leaves the owner free to commit and checkpoint.
- **Contention.** An owner committing with `busy_timeout=0` at the record’s paces while
  the viewer refreshes through the access table’s policy; no commit is refused at any
  pace.
- **Browserless sessions** under `tests/dom/` drive the production table module through
  sort in both directions, filter, paging, opening a record, a position-named record
  after a change, a live change that adds rows above and below the viewport, a removed
  column, pause and resume, the busy state, an exhausted budget, and keyboard movement
  across cells, with invariants on scroll anchor and focused key.
- **Bounds.** Each constant’s measurement is recorded beside it; a large generated table
  checks that a page in key order or on an indexed column costs an index seek, in both
  directions and deep in a column’s null rows, and that an unindexed sort past the
  threshold is refused rather than run.
- **Paint-exempt rows** only for clamping, sticky positioning, and the flash, each named
  with its evidence in the
  [Parity Registry](../../architecture/arch-parity-registry.md).

## Rollout Plan

Every phase ships in the single artifact.
Phase 3 changes what `.csv` and `.tsv` files open as by default, Phase 4 what SQLite
files open as, whatever their extension, and Phase 7 adds a Table tab to JSON and YAML
files as Decision 12 settles it; each changelog fragment says so.
The SDK version bump in Phase 1 is a hard gate for installed plugins, as intended.

## Open Questions

- Should a directory of SoftSchema records sharing one contract open as one table, as a
  knowledge base’s folders would?
  The protocol supports it; the open question is the kind rule and the cost of reading
  every file.
- Should a record list be typed by its SoftSchema contract?
  The contract registry is keyed by an envelope a bare list does not have, so this needs
  a rule for naming a list’s contract.
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
  [security](https://sqlite.org/security.html),
  [How To Corrupt](https://sqlite.org/howtocorrupt.html) (section 2.2, POSIX locks)
- [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md)
- [Plugin System](../../architecture/arch-plugin-system.md),
  [Live Delivery](../../architecture/arch-live-delivery.md),
  [Parity Registry](../../architecture/arch-parity-registry.md)
- [Rendering Large Content](../../../large-content-rendering.md),
  [Design System](../../../design-system.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
