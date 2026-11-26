# Feature: SoftSchema Collection Tables

**Date:** 2026-11-26

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In progress (epic `mb-zuiq`: `mb-h91v` upgrade, `mb-znlo` SoftSchema API,
`mb-ibo7` plugin). The plugin depends on a released upstream collection API. Research:
[Tables Over Folders of SoftSchema Records](../../research/research-2026-11-26-softschema-collection-tables.md).

## Overview

A folder of SoftSchema records opens in Metabrowser as a table: one row per record, one
table per contract, columns from the compiled schema, and records linked to each other
by their IDs.
Opening `universe2026-md/kb/people/` shows 577 people as a table that links
each affiliation to its organization and each talk to its session, the way Paraverse’s
knowledge base browser does, without a database server.

The table reads from a **collection index** that a built-in `softschema` plugin keeps in
Metabrowser’s cache.
The index rolls up every record and every schema under the collection’s root once: it
reads each record, resolves its schema, validates it, and repairs in memory what can be
repaired. After that, it updates only what changed.
A request reads the index, never the files, so a warm table opens as fast as any other
table, and a bad record costs one row’s values, never the table.

The format work lives in SoftSchema, not here.
SoftSchema gains a collection API that scans a tree, binds each record to its schema,
validates in batch, repairs in memory, describes fields, and refreshes by stat; the
plugin calls it and keeps only what is Metabrowser’s: where the index is stored, the
worker that builds it, the table mapping, references, and the views.
Each SoftSchema release that makes this faster or more tolerant reaches Metabrowser as
an upgrade, and Paraverse and the knowledge base pipelines can use the same API.

## Goals

- **A folder of records is a table.** A folder whose subtree holds SoftSchema artifacts
  is offered a Table view: one table per contract, whatever folders the records sit in.
- **Schemas are found where they live.** By each record’s own `softschema.schema`
  pointer, and failing that by contract, from the compiled schemas under the collection
  root, without a configuration file.
- **Fast after the first read.** A collection index in the plugin’s cache directory,
  updated incrementally: a changed record is reread, a changed schema revalidates its
  records from payloads the index already holds, an added or removed file updates its
  rows, and an unchanged tree costs a stat walk.
- **Never fails hard.** Every record that can be read is a row that states its own
  condition (valid, repaired, invalid, unbound, unreadable), and a collection’s problems
  are a table of their own.
  One record, field, or schema can fail only itself.
- **Linked records.** Fields that hold another record’s ID link to it; each record lists
  the records that refer to it.
  The ID prefixes come from the data, not from a hand-kept list.
- **Paraverse’s browsing, generically.** A record view that draws nested shapes as
  sub-tables and the Markdown body as a document, and a collection overview with each
  table’s count, field coverage, and problems.
- **Format logic upstream.** Scanning, binding, validating, repairing, describing, and
  refreshing a collection are SoftSchema library calls, so an upgrade swaps in a better
  implementation with no change to the plugin.
- **Parity.** Every route and state has a `metab` equivalent and a golden, over a
  committed fixture collection that includes every kind of bad record.

## Non-Goals

- **Editing records** or writing repairs back to files.
  Repair and conform run in memory; `softschema repair` and `softschema conform` are the
  tools that write.
- **Executing models.** Validation uses compiled schemas only; no Pydantic or Zod model
  is imported, so opening a folder runs no code from it.
- **Collections on a Git pin.** The index reads a served folder.
  A Git revision’s folders offer no view today, and this plan keeps that.
- **Full-text search across collections**, and graph drawings of references.
- **Domain styling.** Kind colors, groupings, and hand-picked columns belong to a
  downstream plugin (Paraverse’s), which can build on this one.
- **A record list inside one file** (`faq.yaml`, `media.yaml`): the structured plugin’s
  record-list table already shows it.

## Background

The [research brief](../../research/research-2026-11-26-softschema-collection-tables.md)
has the format, the surveyed collections, the measurements, and the options.
The facts that shape this plan:

- **Collections.** Universe’s `kb/` is 4,977 artifacts in 18 contracts; its schemas live
  in `kb/_schemas/`, and each record points at one with a relative path such as
  `../_schemas/person.schema.yaml`. One contract can span many folders (`accounts/`
  holds one contract in eleven), and folders nest seven deep.
  Metabrowser’s own `explorations/performance-loop/experiments/` keeps its schema beside
  72 records and 84 files that are not records.
- **Cost.** Over Universe’s `kb/` in a 4-processor container: a stat walk is 15 ms;
  PyYAML’s C loader reads every record in 1.4 s; the pinned SoftSchema 0.8.1, reading
  with pure-Python ruamel, takes 34 s, and reading plus `validate_artifact` about 88 s.
  SoftSchema 0.9.0 reads C-first with `ruamel.yaml.clib`, 4 to 7 times faster with
  identical results, which puts a cold read at an estimated 5 to 8 s. A cache is still
  required, and it makes the cost one-time.
- **Metabrowser already has the table.** The table plugin was modeled on Paraverse’s
  browser, and the `TableSource` protocol has multiple tables per source, `FieldRef`
  references, back-reference counts, and `ref=` filters.
  What is missing is a source over a folder: `open_table_source` resolves one file and
  classifies it, and no kind can match a directory.
- **The tabular plan left this open**
  ([plan-2026-11-19-tabular-data-and-live-sqlite.md](plan-2026-11-19-tabular-data-and-live-sqlite.md#open-questions)):
  “the open question is the kind rule and the cost of reading every file.”
  This plan answers the kind rule with a folder offer, and the cost with the index.

## Design

### Approach

```text
  folder opened ──offer (bounded sniff)──► Table view offered on the folder
       │
       ▼
  collection root (nearest ancestor holding the records' schemas, inside the served root)
       │
       ▼
  collection index  ◄── background builder (single-flight per root)
  plugins/softschema/collections/<root-digest>/index.sqlite
    files    one row per file seen: stat, profile, contract, schema, payload, state
    schemas  one row per compiled schema: stat, sha256, contract, field model
    links    record → record, by ID, with the field path that holds it
       │
       ▼
  in-memory tables (one per contract) ──► TableSource ──► /api/plugin/table/*
                                      └─► /api/plugin/softschema/{collection,describe}
```

### Where the Code Lives

| Concern | SoftSchema (library and CLI) | Metabrowser `softschema` plugin |
| --- | --- | --- |
| Finding artifacts in a tree, sniffing before parsing | Yes | Passes the root and the ignore rules |
| Binding schemas: pointer, then contract index | Yes | Passes the served root as the boundary |
| Reading (C-first, JSON path) and batch validation | Yes | — |
| In-memory repair and conform, record states | Yes | — |
| Field model (types, lists, enums, `$defs`, patterns) | Yes, extending `SchemaView` | Maps it onto `TableField` |
| Incremental refresh by stat and schema digest | Yes, as a refresh that reports what changed | Decides when to call it |
| Persisting the index | A serializable snapshot | Stores it in the plugin cache directory |
| Collection root, folder offer, worker thread | — | Yes |
| Tables per contract, references, `FieldRef`s | — | Yes |
| Routes, views, goldens | `softschema` CLI over a folder, with its own goldens | Yes |

Everything below marked **(SoftSchema)** is specified here for what Metabrowser needs
from it; its design is settled in SoftSchema’s own plan, under its parity process, which
decides whether the TypeScript package gains the API in the same release.
Until a SoftSchema release has it, nothing in Metabrowser reimplements it.

### Finding Records (SoftSchema)

A file is a candidate when its name ends in `.md`, `.yaml`, `.yml`, or `.json`, and it
is not under a hidden or ignored path (the inventory’s ignore rules).
A `.json` file qualifies because JSON is YAML and the spec resolves a fenceless mapping
with a root `softschema:` block as `pure-yaml`.

A candidate is a record when its metadata parses (`parse_schema_metadata`). Before
parsing, a sniff reads only up to the closing fence (9 µs per file measured), so a
Markdown file with no frontmatter, or frontmatter with no `softschema:` key, costs no
parse. A file that is not a record is remembered by its stat, so it is not sniffed again
until it changes.

Compiled schemas (`*.schema.yaml`, `*.schema.json`) under the root are schemas, not
records, and are indexed separately.

### Finding the Collection Root

The opened folder is not always the right scope: `kb/people/` holds people, but their
schema is in `kb/_schemas/` and their organizations in `kb/organizations/`.

1. Sniff a bounded sample of records in the opened folder (descending into subfolders,
   bounded, when it holds no records itself, as `kb/` does).
2. Resolve each sampled record’s schema pointer.
3. The root is the nearest common ancestor of the opened folder and those schemas, kept
   inside the served root.
   Apply the same inventory ignore policy to discovery and explicit pointers.
   When the sample offers no eligible schema, start with the opened folder.

For `kb/people/` and `kb/accounts/x/` the root is `kb/`; for the experiments folder it
is the folder itself.
The opened folder becomes a path filter on the root’s tables, so every subfolder shares
one index and references into sibling folders resolve.
This is a discovery heuristic.
The index must identify the scope it scanned and report when a bound cuts discovery.

### Finding Each Record’s Schema (SoftSchema)

In order, the first that yields a readable compiled schema:

1. **The record’s pointer**, `softschema.schema`, resolved from the record’s directory
   with the package’s safe-path helpers.
   It must stay inside the served root.
   Reject absolute paths, paths through symlinks, and schemas declaring a different
   contract.
2. **The contract index**: every compiled schema under the root whose root
   `x-softschema.contract` equals the record’s contract ID. Identical schema digests are
   equivalent. When several distinct digests claim the contract, a record without a
   usable pointer stays unbound, and the overview reports the ambiguity.
3. **None.** The record is `unbound`: it is a row, and its table’s columns come from the
   payloads observed instead of a schema.

Schemas are read with SoftSchema’s reader and prepared once per digest; `$ref` stays
offline, as SoftSchema requires.
A schema that does not load (`schema_invalid`) makes its records `unbound`, with the
schema’s error in the overview.

The spec puts a host registry above the document’s own pointer.
A viewer wants the reverse: the document’s pointer first, the contract index only as a
fallback. SoftSchema’s plan settles how a caller asks for fallback binding.

### Reading and Validating (SoftSchema)

One reader: SoftSchema’s portable reader, C-first, so every value shown is the value any
SoftSchema consumer reads.
The plugin requires the SoftSchema release with the collection API and
`ruamel.yaml.clib`; `softschema.yaml_parser_mode()` reports `c-first` in
`metab --doctor`.

For each changed record the builder reads it, extracts metadata, envelope, host keys
(`title`), and payload, and validates the payload against its bound schema with a
validator prepared once per schema digest.
Where the read fails, it tries `repair_yaml_text` on the YAML region; where validation
fails on a string type, `conform` with writing off.
A repaired or conformed record shows the repaired values and is marked so.
Nothing is written to the record’s file.

Records are processed in an order that fills a table quickly (the opened folder first),
and the index is committed in batches, so rows appear as the build runs.
If the measured C-first build is still too slow for a first open, a schema-free read of
the opened folder first, with verdicts after, is the fallback design; it is not planned
until a measurement asks for it.

### Record States (SoftSchema)

Every row carries one state, in the synthetic `$state` column, which the table can
filter and sort on:

| State | Meaning | What the row shows |
| --- | --- | --- |
| `valid` | Read portably; the bound schema accepted it | Values |
| `repaired` | Valid only after an in-memory repair or conform | Values, marked, with the repairs |
| `invalid` | The bound schema rejected it | Values, with each error at its field |
| `unbound` | No schema could be bound | Values, typed from observation |
| `pending` | Read, and waiting for revalidation after its schema changed | Values |
| `unreadable` | No reader could parse it, even after repair | Path and error only |
| `malformed` | Its `softschema:` block or envelope is invalid | Path and error only |

`unreadable` and `malformed` records have no contract to group by, so they appear only
in the Problems table and in the overview’s counts.
A cell whose value does not have its field’s declared type is drawn as its raw value
with a mismatch mark, filters and sorts as text, and never affects another cell.

### The Index

SoftSchema’s collection API returns the index’s content (per file: stat, profile,
metadata, payload, state, errors, repairs; per schema: digest, contract, field model)
and refreshes it against the tree, reporting what changed.
The plugin persists it: one SQLite database per collection root, at
`plugin_cache_directory("softschema")/collections/<digest of the root's real path>/`.
SQLite gives atomic incremental updates and survives a crash mid-build.
The agents plugin’s summary store is the precedent.
Key cache reuse by the resolved served boundary, collection root, and effective ignore
policy.
The same collection path can produce different results under a different boundary
or policy. The tables below are the plugin’s storage; the invalidation rules are
SoftSchema’s refresh, which the plugin runs.

- **`meta`**: the index format version, the plugin’s version, SoftSchema’s version, and
  the root. A mismatch discards the index and rebuilds it.
- **`files`**: one row per candidate file: relative path, device, inode, size,
  modification time, kind (record, schema, other), profile, contract, envelope, declared
  status, schema path, host keys, payload as JSON, state, error records, repairs, and
  the digest of the schema its verdict was computed against.
- **`schemas`**: path, stat, SHA-256 of its content, contract, load error, and its field
  model (below).
- **`links`**: source record, field path, target ID; resolved to target rows when the
  tables load.

**Invalidation**, all by comparing what is stored with what is there:

- A file whose stat changed is reread and revalidated.
- A file that appeared is sniffed; one that disappeared loses its row and its links.
- A schema whose digest changed sets its records’ verdicts to `pending`; their payloads
  are kept, so no record is reread.
- Records whose schema pointer or contract changed are rebound.

**Freshness.** The source’s `generation()` identifies the snapshot the worker published.
Filesystem changes and scheduled checks trigger the worker’s stat walk.
Requests read the generation alongside the corresponding rows and links.
A walk bounded by a measured file cap stops there, and the overview says the collection
was cut.

**Unavailable cache.** When `plugin_cache_directory` raises, the index lives in memory
for the server’s life and the overview says `cache: unavailable`, as the agents catalog
does.

**Builder.** One worker thread per root, single-flight, tied to the served root with
`register_root_callback`, and stopped at its next file when the root changes.
Requests never wait for it: a request answers from the index as it stands, and a page
built from an incomplete index says so (a new `PageReason`, `indexing`), so the view
shows progress and refetches.
`metab --api` and the goldens wait for a complete index, bounded, as the agents catalog
`complete()` does.

### Tables and Fields

The source’s `tables()` lists one table per contract with rows under the opened folder,
plus `Problems` when any record has one.
A table’s ID is the contract ID; its label is the contract’s name, or the schema’s
`title`.

Fields come from SoftSchema’s field model, computed once per schema digest.
It extends `SchemaView`’s `FieldInfo` with what a column needs and Paraverse’s
`describe_fields` already derives: title, list-ness, `format`, `pattern`, and the `$def`
a nested value names, in the order `id`, required, then the rest.
The plugin maps it onto `TableField`:

| Schema | `TableField` |
| --- | --- |
| `string` | `text`; `date` and `datetime` from `format`; `format: url` from an `http(s)` pattern |
| `integer`, `number`, `boolean` | `integer`, `real`, `boolean` |
| `enum` | `enum` |
| An array of scalars | the item type, with `list` |
| An object, a `$ref`, or an array of either | `json`, with the `$def` named for the record view |
| A typed-ID pattern | a `FieldRef` to the table whose IDs have that prefix |

Synthetic fields come first in the field list and are hidden by default except `$state`:
`$path` (the record’s file, a link), `$state`, and each host key (`$title`). A payload
field that collides with a synthetic name keeps its own name and the synthetic one is
suffixed.

**Default columns** are chosen from coverage, not from a list: the key, a label field
(`name` or `title` when the schema has one), then scalar fields in field order whose
coverage passes a measured threshold, up to the table view’s column budget.

**Unbound tables** type each field from the values observed: a field whose values are
all one scalar type gets that type, and anything else is `json`.

**Versions.** Records of `Person/v1` and `Person/v2` under one root are two tables.
Merging versions, as Paraverse does across datasets, is an open question.

### References

- **Keys.** Use the record’s relative path as the stable row key.
  Index its `id` for cross-record links.
  An ID with multiple target rows stays unresolved and is reported as ambiguous, so
  duplicate or missing IDs leave all rows addressable.
- **Learned prefixes.** For each keyed table, the builder records the prefixes of its
  IDs (`person:` for every Person record).
- **Reference fields.** A field whose pattern’s alternation names prefixes
  (`^(gh|acct):...`) refers to the tables with those prefixes.
  One target table becomes a `FieldRef`; several become a field the record view and
  cells resolve per value.
- **Nested references.** The builder walks each payload for strings equal to a known ID
  at any depth (`affiliations[].organization`), and stores them in `links` with their
  path. The record view shows them as links, and the target’s record lists them as
  back-references, grouped by referring table and top-level field.
- **Dangling IDs** are drawn as unresolved, not as errors.

### Activation: the Folder Offer

The plugin declares a Table view on the `folder` kind, gated by an offer
(`softschema.offer:offers_collection`), as the agents plugin gates its views.
The predicate:

1. answers yes when the index already places the folder inside a collection root;
2. otherwise reads a bounded number of the folder’s entries and sniffs a bounded number
   of candidate files for a `softschema:` block, descending one level into subfolders
   when the folder holds none itself, and checks for a `_schemas/` or `schemas/` folder
   or a `*.schema.yaml` file whose root carries `x-softschema`.

Both bounds are set from measurements in Phase 1 and recorded beside their constants.
The folder keeps its Overview as the default.
The offer adds a Table tab.

### Table Routes Over a Folder

`open_table_source` resolves a file today.
It gains one branch: when the path is a served directory, it asks each folder table
source’s offer, in discovery order, and opens the first that accepts.
The manifest declares it as `[[table_source]] kind = "folder"` with an `offer`, which
the manifest validator allows only for the `folder` kind.
`TableHandle` gains a directory form (its `local_path` a directory, its `ref` the
folder’s identity), and `TableHandle.read_window` refuses on it.

A folder cannot address a table as `<path>/<table>`, as a container file does, because
the segment would collide with a child’s name.
The table routes and the table view gain an optional `table` query key for a source over
a folder; a file source keeps its path form.
These are internal contracts (`/api/*` and the view’s address) and change everywhere in
one commit.

### Views

- **Table** (Phase 3): the table plugin’s view, mounted with the folder’s path and the
  selected table. A collection with one table opens it; with several, the overview.
- **Overview** (Phase 3): the collection’s root, build state and cache state, each
  table’s count, problem count, and field coverage, the schemas and which records bind
  to each, and links into each table and the Problems table.
  It is the Table view’s landing page when there are several tables.
- **Record view** (Phase 3): the table plugin’s record view, extended through a
  `describe` hook the softschema plugin serves: fields in field-model order; nested
  objects as a definition list; a list of objects as a sub-table over its `$def`’s
  fields; references as links with hover cards; validation errors at their fields;
  repairs listed; the Markdown body rendered below the fields, as reader-facing text;
  and the raw payload.
  Whether this is the table plugin’s extension point or the softschema plugin’s own
  record drawing is settled against the object model plan’s detail view.

### Routes

| Route | Answers |
| --- | --- |
| `/api/plugin/table/{tables,schema,rows,record,card}?path=<folder>&table=<contract>` | The existing table routes, over a folder |
| `/api/plugin/softschema/collection?path=<folder>` | Root, build and cache state, tables with counts and coverage, schemas, problem counts |
| `/api/plugin/softschema/describe?path=<folder>&table=<contract>` | The field model with `$defs`, for the record view |

Each answers from the index; none reads a record on the request path.

### Bounds

Every bound is measured before it is set, and documented beside its constant:

- files walked per collection, and the cut the overview reports past it;
- entries and files the offer sniffs;
- bytes read from one record, reusing `FRONTMATTER_MAX_BYTES` for frontmatter and a
  measured cap for a pure YAML or JSON record, past which the record is `unreadable`
  with the reason;
- records the builder processes between commits, so a cancelled build keeps its work;
- the wait `metab --api` allows for a complete index.

### Imports

Importing `metabrowser` must not load `softschema` or `jsonschema`
(`tests/test_plugin_public_api.py`). The offer, the routes, and the builder import them
inside their functions, as the GitHub sidekick does.

## Decisions

1. **Offer the Table view alongside Overview.** Discovery examines a bounded sample.
   Keeping Overview as the initial view gives folder links and keyboard navigation a
   stable destination as files are added.
2. **The index root is the nearest ancestor holding the records’ schemas**, with the
   opened folder as a filter, so references resolve from any subfolder.
   Alternative: index only the opened subtree.
3. **One reader, SoftSchema’s, C-first.** Upgrade to SoftSchema 0.9.1 and add
   `ruamel.yaml.clib` after the supply-chain review, rather than a second, faster reader
   in Metabrowser.
4. **The collection API goes in SoftSchema first**, with the shared contract and CLI
   tested on Python and TypeScript under SoftSchema’s parity process.
   The plugin starts once a release has it.
5. **Three phases:** upgrade and measure; the collection API in SoftSchema; then the
   plugin, its table, overview, and record view.

## Implementation Plan

### Phase 1: Upgrade SoftSchema and Measure (Metabrowser)

- [x] Supply-chain review of `ruamel.yaml.clib` per
  [SUPPLY-CHAIN-SECURITY.md](../../../../SUPPLY-CHAIN-SECURITY.md), within its cool-off.
- [x] Upgrade to SoftSchema 0.9.1 and frontmatter-format 0.5.1 (first-party), add
  `ruamel.yaml.clib`, and adapt to 0.9.0’s changes: results now report `execution`, and
  some raw characters are newly refused.
  Metabrowser’s own contracts, cache records, and guided-review collections must still
  read, which the existing corpus and round-trip checks show.
- [x] `metab --doctor` reports SoftSchema’s parser mode.
- [x] Add a repeatable generated and existing-tree benchmark.
  Compare both parser modes and fail if they disagree on record counts, parsed data, or
  verdicts.

The [benchmark](../../../../devtools/bench_softschema_collection.py) on macOS arm64 and
CPython 3.14.7 took the median of three trials in each mode.
The filesystem cache was warm and each trial started with an empty validator cache.
The corpus commits are the ones pinned in the research brief.

| Corpus | Valid records | Read and bind, C-first / pure | Validate and hash, C-first / pure |
| --- | ---: | ---: | ---: |
| Generated | 2,000 | 1.18 s / 2.54 s | 0.15 s / 0.16 s |
| GitHub Universe | 4,971 | 8.05 s / 41.98 s | 3.23 s / 3.29 s |
| Patch the Conference | 132 | 0.17 s / 0.63 s | 0.27 s / 0.42 s |

The modes agreed on all three collections.
The Universe walk took about 0.10 s on this drive.
Reading and validating that corpus still takes about 11 s in C-first mode, so the cold
build and refresh walk belong in the worker.
The benchmark does not exercise the eventual offer, incremental index, or browser, which
need their own measurements before their limits are set.

### Phase 2: The Collection API (SoftSchema)

Planned and built in SoftSchema’s repository, under its own spec and parity process.
What Metabrowser needs from it:

- [ ] A scan of a tree that sniffs before parsing, honours caller ignore rules and a
  boundary the schema pointers may not leave, and returns per-file results.
- [ ] Schema binding by the record’s pointer, then by a contract index of compiled
  schemas under the root, as a caller-chosen fallback order.
- [ ] Batch validation with validators prepared once per schema digest, and record
  states with errors, in-memory repairs, and conform results.
- [ ] The field model: `SchemaView` fields with title, list-ness, `format`, `pattern`,
  and `$def` names.
- [ ] A serializable index and a refresh that rereads only changed files and revalidates
  only records whose schema changed, reporting what changed.
- [ ] A command over a folder (for example `softschema scan kb/ --json`) that prints the
  collection’s tables, counts, and problems, with goldens in SoftSchema.

### Phase 3: The Plugin, Its Table, Overview, and Record View (Metabrowser)

The table works end to end over any folder of records, with every state visible, and
browses as Paraverse’s does.

The folder preview uses the collection API from
[SoftSchema PR #78](https://github.com/jlevy/softschema/pull/78). It opens the Patch the
Conference corpus as nine contract tables covering all 132 records, with a reusable
index and the shared table grid.
The preview tests pin cross-folder links, exact inbound relationship filters, source
links, and stable generations.
The full rollout requires a released SoftSchema dependency.

- [ ] Fixture collection `tests/fixtures/softschema-collection/`: a small knowledge base
  with schemas in `_schemas/`, records nested in subfolders, Markdown and YAML and JSON
  records, references between tables, two versions of one contract, and one record of
  each bad kind: unparseable, repairable, conformable, invalid, unbound, malformed
  metadata, ambiguous envelope, a schema pointer leaving the served root, a
  contract-only record, and an invalid schema.
- [ ] Core: a `folder` table source with an offer in the manifest model and validator;
  the directory branch of `open_table_source` and the directory `TableHandle`; the
  `table` query key in the table routes and the table view’s address; the `indexing`
  page reason in the protocol and the view.
- [ ] `builtin_plugins/softschema/`: manifest, the offer, collection root resolution,
  the index store over SoftSchema’s collection API, the builder thread, learned prefixes
  and links, and the `TableSource` over the in-memory tables (on the table plugin’s
  `memory.py`).
- [ ] The `collection` route, and `complete()` for `metab --api`.
- [ ] Goldens: `--api` over the table routes and the `collection` route on the fixture,
  including the Problems table and a subfolder filter; `--show` on the fixture’s folder;
  an incremental case that edits a record, a schema, and adds and removes a file between
  requests.
- [ ] The Overview: tables, counts, coverage, schemas, problems, build and cache state.
- [ ] The `describe` route and the SoftSchema record view: nested shapes, sub-tables,
  references and back-references with their paths, errors at fields, repairs, the body,
  and the raw payload.
- [ ] Hover cards for references, from the table plugin’s card route.
- [ ] Interaction sessions over the production modules for the overview’s and record
  view’s states, with goldens; paint exemptions only for what is paint.
- [ ] A check against both real knowledge bases (Universe and Patch the Conference),
  recorded in the plan, without committing their data.
- [ ] Parity rows, the
  [views, models, and routes map](../../architecture/arch-views-models-routes.md), a
  user guide section, and a changelog fragment.

Phase 3 is the largest; if its stack passes eight pull requests, the overview and record
view split into a fourth phase.

## Testing Strategy

- **Golden transcripts** over the fixture for every route and every record state, as the
  parity registry requires.
- **Invariant tests**, not restatements: a bad record never removes another record’s
  row; a changed schema revalidates without rereading records; a second request on an
  unchanged tree does no parse; the index after an incremental update equals a fresh
  build of the same tree; no route reads a record file.
  The collection API’s own invariants are tested in SoftSchema.
- **Fault injection:** a cache directory that cannot be created, a build cancelled
  mid-pass, a file deleted between the walk and the read, a schema that changes during a
  build.
- **Browserless sessions** for the view states, over the exact production JavaScript.
- **The benchmark** is rerun before any bound changes.

## Rollout Plan

Phase 1 ships on its own: a dependency upgrade with no visible change but speed.
Phase 2 ships as a SoftSchema minor release.
The plugin ships built in, in the single artifact, pinned to that release.
Opening a folder of SoftSchema records offers a Table view alongside Overview.
The table protocol’s additions are internal contracts and land with every consumer in
the same commit; if they change an SDK surface, `PLUGIN_SDK_VERSION` moves with every
built-in manifest.

## Open Questions

- Should two versions of one contract merge into one table, as Paraverse merges
  datasets? If so, the merge belongs in SoftSchema beside the field model.
- Should typed-ID references become a SoftSchema convention (an `x-softschema` field
  annotation naming the target contract) rather than prefixes the plugin learns?
- Should a collection file at the root name extra schema folders, groupings, or default
  columns, once a collection needs what the data cannot say?
- Should a reference field with several target tables become several `FieldRef`s, which
  the protocol does not model today?
- Should a single record file opened on its own (`people/aaron-reich.md`) gain the same
  SoftSchema record view as a tab beside its Markdown view?
- Should validation also report the record’s Markdown body drifting from its payload,
  when a schema marks the fields the body restates?

## References

- [Research brief](../../research/research-2026-11-26-softschema-collection-tables.md)
- [SoftSchema spec](https://github.com/jlevy/softschema/blob/main/docs/softschema-spec.md)
  and [guide](https://github.com/jlevy/softschema/blob/main/docs/softschema-guide.md)
- [Paraverse](https://github.com/jlevy/paraverse) `db/src/paraverse_graph/`:
  `schemas.py`, `web/js/table.js`, `web/js/record.js`, and its
  [browser plan](https://github.com/jlevy/paraverse/blob/main/docs/project/specs/done/plan-2026-10-24-kb-browser.md)
- [Tabular data plan](plan-2026-11-19-tabular-data-and-live-sqlite.md) and
  [object data model plan](plan-2026-11-14-object-data-model-and-views.md)
- [Plugin System](../../architecture/arch-plugin-system.md),
  [Parity Registry](../../architecture/arch-parity-registry.md)
- `src/metabrowser/table_source.py`, `builtin_plugins/table/`,
  `builtin_plugins/agents/catalog.py`, `builtin_plugins/fsqlite/`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
