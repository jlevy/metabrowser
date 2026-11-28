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
The folder preview reads a bounded eager SoftSchema scan.
The first implementation may keep every admitted record, schema, value, body, and link
in memory and serve the shared Table routes from that index.
Universe is its real acceptance corpus.
The later design targets collections of 100,000 to millions of rows.
It projects values in bounded batches and can fetch full detail from the selected source
revision.

The format work lives in SoftSchema, not here.
SoftSchema gains a collection API that scans a tree, binds each record to its schema,
validates in batch, repairs in memory, describes fields, and refreshes by stat; the
plugin calls it and keeps only what is Metabrowser’s: where the index is stored, the
worker that builds it, the table mapping, references, and the views.
Each SoftSchema release that makes this faster or more tolerant reaches Metabrowser as
an upgrade, and Paraverse and the knowledge base pipelines can use the same API.

## Shared Browser Components

Use the Files scan progress component for the initial index.
It supplies the same spinner, type and muted color.
Keep the last published catalog and grid visible during refresh.
Use the same table catalog and grid as SQLite, with addressable links to tables, records
and their source files.
Use the shared parent-navigation button for returns to the table or catalog.
[Design system](../../../design-system.md#data-tables).

Nested values will use the main app’s schema-free structured-data views.
Equivalent JSON, flow YAML and block YAML get the same Table and Tree presentation.
Source opens the original file or excerpt when a field has a reliable source address.
The main app also shares these views with Markdown frontmatter, standalone files and
diffs. [Structured data views plan](plan-2026-11-26-structured-data-views.md).

Paraverse’s catalog pairs entity links with numeric totals.
The shared Metabrowser catalog applies that pattern to database tables and collection
contracts.
Paraverse also keeps a record’s identity visible as columns disappear and uses
compact sub-tables for lists of objects.
Preserve the record address in Metabrowser’s windowed grid and carry the compact nested
layout into the core structured views.
Use on-demand drill-down for deeper values and large lists.
Paraverse’s graph labels and edge groups belong to its domain model.
[Paraverse browser architecture](https://github.com/jlevy/paraverse/blob/main/docs/project/architecture/arch-2026-10-24-kb-browser.md).

Keep the shared catalog and grid in the Metabrowser Table plugin.
Evaluate a cross-application package after the apps have a common model for row
identity, paging, and navigation.
Paraverse reads graph-specific routes and uses hash navigation.
Metabrowser’s windowed table is also used for SQLite, delimited files and structured
data.

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
  The first rollout serves filesystem folders.
  Phase 5 covers cached Git revisions.
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
    files    one row per observed path and revision
    schemas  one row per compiled schema and binding identity
    cells    projected row values and labels by stable row key
    links    source row and field path to target ID
       │
       ▼
  indexed tables (one per contract) ───► TableSource ──► /api/plugin/table/*
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
| Persisting the index | Runtime-local snapshot for eager scans, proposed stream of observations for larger trees | Owns SQLite generations, projected cells, ID lookups, and link indexes |
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

The plugin uses SoftSchema’s portable reader and requires a release with the collection
API. A stock installation uses the pure reader.
On compatible CPython builds the `yaml-accelerator` extra installs `ruamel.yaml.clib`
and enables C-first mode.
`metab --doctor` reports the active parser.

For each changed record the builder reads it, extracts metadata, envelope, host keys
(`title`), and payload, and validates the payload against its bound schema with a
validator prepared once per schema digest.
Where the read fails, it tries `repair_yaml_text` on the YAML region; where validation
fails on a string type, `conform` with writing off.
A repaired or conformed record shows the repaired values and is marked so.
Nothing is written to the record’s file.

Prioritize declarations and cells under the opened folder on a cold build.
Publish the coverage of that folder separately from collection-wide validation and link
resolution. A row can appear with validation pending.
Only a completed structural check can give it a passing verdict.

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

The preview stores one serialized eager scan in SQLite, restores it on startup, and
groups its materialized records in memory.
Its worker still opens every eligible file on a cold scan.
An eager in-memory index is sufficient for the first implementation.
The steps below describe the later large-collection index and depend on the proposed
operations in `docs/softschema-collection-design.md` in
[the SoftSchema collection change](https://github.com/jlevy/softschema/pull/78).

1. **Open the catalog.** Keep the automatic folder offer bounded.
   A host can opt a root into collection browsing and specify a fallback catalog, such
   as `_schemas/` containing compiled YAML or JSON, or a JSON-only catalog in a tree
   that guarantees that convention.
   Key the index by served boundary, collection root, effective ignore and catalog
   policies, and storage and reader versions.
   An ordinary folder pays only for the offer.
   The default discovers all supported schema suffixes within the root.
   A safe explicit record pointer can bind outside a narrow fallback catalog.
   Publish known schemas early with count and membership marked unknown.
   Unbound records can introduce additional contracts.
2. **Index references.** Stream candidate paths and revisions to the staging database.
   Ask SoftSchema to inspect each declaration and record its profile, contract,
   envelope, status, and pointer.
   Preserve unknown membership and per-file diagnostics.
   Inspection of pure YAML and JSON can require reading the whole file.
   Discard parsed values as each file finishes.
   Markdown inspection can stop at the closing fence when the body is outside the
   request. No full-tree list or collection-sized payload buffer should be needed to
   serve the first page.
3. **Project values and links.** For each record needed by the table, ask SoftSchema for
   its payload at the observed revision.
   Write the requested or indexed cells, label, source path, state, diagnostics, and
   binding identity. Retain enough source material to reconform after a schema change, or
   reread the affected file.
   Store IDs with all matching row keys and outgoing target IDs with source row keys and
   nested field paths. Index target IDs for backlink and `ref=` queries.
   See [References](#references) for duplicate IDs and cross-folder lookup.
   Exact sorting, filtering, and counts require coverage of all relevant rows.
4. **Publish a generation.** Write batches under a staging generation.
   On the first build a published partial generation can serve the opened folder, with
   explicit coverage for rows, ordering, links, and counts.
   During refresh keep the previous generation readable until the replacement is
   published atomically.
   A cancelled walk cannot remove unseen members.
   Reconcile deletions only within a fully listed scope.
   Rebind fallback records when the set of eligible schema digests changes, even if
   their source files did not change.
   Bind rows, cursors, link targets, and diagnostics in each response to the same
   published generation.
5. **Refresh one changed file.** A watcher can mark a path dirty and coalesce repeat
   notifications. Verify its current revision and inspect it through the same SoftSchema
   reader used for a cold build.
   In one transaction, remove that path’s old contract membership, projected cells, ID,
   and outgoing edges, then insert its new facts.
   Update the affected contract counts and indexes.
   Record target ID changes on both sides so incoming links and duplicate-target status
   resolve correctly when a file is renamed, changes ID, or changes contract.
   A schema change uses the reverse binding index to revalidate affected rows.
   A changed fallback catalog can also affect records that previously had an ambiguous
   or missing binding. Update only the relevant rows and advance the published
   generation. Retain hot metadata and pages over the durable SQLite index and invalidate
   dependent pages, sort indexes, and backlinks.
   Readers already using the previous generation finish against it.
   A periodic reconciliation catches missed events.
   An overflow or loss of coverage schedules a scan of the affected scope.
6. **Load detail.** Pages, cards, and backlinks read the projection.
   When full values or the Markdown body are requested, materialize just the selected
   record through SoftSchema’s revision-checked reader.
   A changed or missing source must yield a stale or gone result and schedule a refresh.
   A cached old revision can supply detail only when its bytes and binding match the
   requested generation.

Keep a bounded in-memory index available for small collections when the plugin cache is
unavailable. If a large collection cannot spool to disk, report the cache condition and
extent of coverage. Record the time to first useful page and peak memory before choosing
batch sizes and retained fields.

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
a folder. In the view address, an empty `table` value opens the catalog.
A file source keeps its path form.
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

Table lists, schemas, row pages, cards, and indexed relationships read the published
generation. Full record detail may load its observed source revision as described in
[The Index](#the-index).

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
3. **One reader, SoftSchema’s.** Upgrade to SoftSchema 0.9.1 and offer its native
   accelerator as a reviewed extra on compatible CPython builds.
4. **The collection API goes in SoftSchema first**, with the shared contract and CLI
   tested on Python and TypeScript under SoftSchema’s parity process.
   The plugin starts once a release has it.
5. **Ship the folder table on the eager collection API.** The first implementation may
   keep all admitted data in memory.
   Deliver disk-backed projection, bounded scrolling, and incremental maintenance for
   larger collections in a subsequent phase.

## Implementation Plan

### Phase 1: Upgrade SoftSchema and Measure (Metabrowser)

- [x] Supply-chain review of `ruamel.yaml.clib` per
  [SUPPLY-CHAIN-SECURITY.md](../../../../SUPPLY-CHAIN-SECURITY.md), within its cool-off.
- [x] Upgrade to SoftSchema 0.9.1 and frontmatter-format 0.5.1 (first-party), add the
  `yaml-accelerator` extra, and adapt to 0.9.0’s changes: results report `execution`,
  and some raw characters are newly refused.
  Metabrowser’s own contracts, cache records, and guided-review collections must still
  read, which the existing corpus and round-trip checks show.
- [x] `metab --doctor` reports SoftSchema’s parser mode.
- [x] Add a repeatable generated and existing-tree benchmark.
  Compare both parser modes and fail if they disagree on record counts, parsed data, or
  verdicts.

The [benchmark](../../../../devtools/bench_softschema_collection.py) on macOS arm64 and
CPython 3.14.7 took the median of three trials in each mode.
Run it with
`uv --config-file uv.toml run --frozen --extra yaml-accelerator python -m devtools.bench_softschema_collection`
on an interpreter that can install the extra.
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

SoftSchema released the filesystem collection API in
[0.10.0](https://github.com/jlevy/softschema/releases/tag/v0.10.0). The integration has
these acceptance requirements.

- A scan of a tree that sniffs before parsing, honours caller ignore rules and a
  boundary the schema pointers may not leave, and returns per-file results.
- Schema binding by the record’s pointer, then by a contract index of compiled schemas
  under the root, as a caller-chosen fallback order.
- Batch validation with validators prepared once per schema digest, and record states
  with errors, in-memory repairs, and conform results.
- The field model: `SchemaView` fields with title, list-ness, `format`, `pattern`, and
  `$def` names.
- A serializable index and a refresh that rereads only changed files and revalidates
  only records whose schema changed, reporting what changed.
- A command over a folder (for example `softschema scan kb/ --json`) that prints the
  collection’s tables, counts, and problems, with goldens in SoftSchema.

### Phase 3: The Plugin, Its Table, Overview, and Record View (Metabrowser)

The standard distribution loads the collection plugin by default.
A custom build can leave out its directory under `builtin_plugins`. Folder Overview and
Treemap, the shared structured views, and the SQLite table source work with the
collection plugin absent.
The SoftSchema library itself remains a runtime dependency for packaged cache contracts
and other existing callers.

The table works end to end over any folder of records, with every state visible, and
browses as Paraverse’s does.

The folder preview uses the API in the
[SoftSchema collection change](https://github.com/jlevy/softschema/pull/78). The shared
grid opened nine contract tables covering 132 records on Patch the Conference and 18
contract tables covering 4,971 records on Universe.
The first Universe scan under concurrent test load exceeded the CLI request deadline.
The background index subsequently supplied all 18 cached tables while another refresh
ran. During a cold build, the shared file-scan status reports paths checked by the
collection discovery walk.
The same index resolves schemas and record links across sibling folders.
The count includes directory and ignored entries checked by the walker.
Artifact reads, parsing, and validation continue after discovery.
A refresh keeps the last published generation visible.
The preview tests pin cross-folder links, exact inbound relationship filters, source
links, and stable generations.
The preview uses the
[published collection release](https://github.com/jlevy/softschema/releases/tag/v0.10.0).
`pyproject.toml` and `uv.lock` pin the release used by the installed plugin.

Use the bounded eager snapshot for this phase.
It can retain a complete collection in memory and rebuild its table projection on
refresh. The first deliverable is a working path from the folder offer through a linked
row and back on Universe.
A narrow schema catalog, disk-backed row projection, page eviction, and single-row index
updates belong to the later phase.

**Checked in the preview**

- [x] The shared Table routes return a folder schema, rows, and a record with a source
  path. The
  [CLI golden](../../../../tests/golden/cli-api-softschema-collection.tryscript.md)
  exercises the normal entry points.
- [x] The folder source registers its offer, folder handle, table adapter, collection
  data hook, and indexing state through the existing plugin and shared Table surfaces.
- [x] The [folder source tests](../../../../tests/test_softschema_table_source.py) cover
  cross-folder references, inbound filters, and generation changes.
- [x] The preview opened the contract tables on Universe and Patch the Conference.
  The cold-start limitation above is recorded separately from the warm result.
- [x] The
  [Universe route run](../../../../explorations/softschema-projection/actual-routes.md)
  exercised an edit that changed both a displayed value and a reference.
  The next generation preserved the row key and updated both inbound counts.

**Remaining first implementation work**

- [ ] Fixture collection `tests/fixtures/softschema-collection/`: a small knowledge base
  with schemas in `_schemas/`, records nested in subfolders, Markdown and YAML and JSON
  records, references between tables, two versions of one contract, and one record of
  each bad kind: unparseable, repairable, conformable, invalid, unbound, malformed
  metadata, ambiguous envelope, a schema pointer leaving the served root, a
  contract-only record, and an invalid schema.
- [ ] Extend the existing goldens with the full diagnostic fixture, including the
  Problems table and a subfolder filter.
  Cover a schema edit and file additions and removals between requests.
- [ ] The Overview: tables, counts, coverage, schemas, problems, build and cache state.
- [ ] The `describe` route and the SoftSchema record view: nested shapes, sub-tables,
  references and back-references with their paths, errors at fields, repairs, the body,
  and the raw payload.
- [ ] Hover cards for references, from the table plugin’s card route.
- [ ] Interaction sessions over the production modules for the overview’s and record
  view’s states, with goldens; paint exemptions only for what is paint.
- [ ] Complete the rollout documentation and add parity evidence for the planned
  Overview and SoftSchema record detail where they introduce new surfaces.

### Phase 4: Bounded Tables for 100,000 to Millions of Rows

This phase is proposed.
The goal is continuous scrolling in either direction through a large table, with bounded
work per page and efficient changes to individual rows.

1. Use the proposed upstream catalog and reference operations to populate the staged
   SQLite projection in [The Index](#the-index).
   Index the sort and filter inputs used by the first measured queries.
   Preserve the first phase’s row identity, null and missing semantics, query ordering,
   link behavior, and count coverage.
2. Keep the existing [row route contract](../../../../src/metabrowser/table_source.py).
   A request supplies its sort, filters, selected columns, `after`, and `limit`. The
   response supplies `next_after`, generation, effective limit, and count coverage.
   The [Table view](../../../../src/metabrowser/builtin_plugins/table/table-view.js)
   already prefetches as the viewport approaches the held rows and renders a window with
   overscan. Its
   [page model](../../../../src/metabrowser/builtin_plugins/table/table-model.js)
   currently appends every decoded page and stops a join when the generation changes.
   Windowing bounds mounted DOM rows today.
   A long scroll still retains all its cells.
3. Use the
   [commit-history window](../../../../src/metabrowser/static/git-history-window.js) as
   the working precedent.
   Commits keeps a bounded decoded-page cache and rebases logical ordinals onto shorter
   physical scroll segments.
   Its [panel](../../../../src/metabrowser/static/git-panel.js) remembers visited page
   cursors for direct replay and follows page links into new territory.
   Give Table a measured row and byte budget for retained pages.
   Keep page anchors for the active query and generation so an evicted page can be
   fetched again when scrolling back.
   Resolve a row by its stable key when restoring focus after opening detail.
   Measure whether saved forward cursors suffice or an indexed seek is needed.
   Commit graph lane checkpoints are specific to the history view.
4. Implement the single-file transaction in [The Index](#the-index), including ID and
   backlink changes. A refresh invalidates affected query pages and marks an old
   continuation expired if it cannot be resumed consistently.
5. Run the [scale acceptance](#end-to-end-scale-acceptance) with a wide fixture at
   100,000 rows and then at million-row scale on suitable hardware.
   Scroll far past the page cache, reverse across an eviction, open a linked row, and
   return to the original position.
   Measure retained client cells and bytes, mounted rows, peak worker memory, and reads
   per page. Repeat a one-file update and compare changes to rows and links with a fresh
   build.

### Phase 5: Tables over Cached Git Revisions

Add a bounded collection reader that enumerates regular blobs from the selected Git tree
and opens their content through the existing blob window reader.
SoftSchema’s reader contract supplies paths and bytes to its existing discovery,
binding, and validation steps.
A missing blob or an exhausted budget makes the scan incomplete.
Keep the existing deferred-binding behavior for incomplete scans.
Symlinks and submodules remain outside the collection.

Give the folder offer, collection route, and table routes one pinned-folder handle.
The offer probes bounded prefixes.
Opening Table starts the index.
Key the published index by repository identity, pinned revision and root tree, and the
collection policy. Reuse it for the immutable pin.
Scope each table to the opened folder while retaining the collection-wide identities
needed for references.
Carry encoded Git paths through table and source links so navigation stays in the
selected revision.

Exercise the same Universe People table in a filesystem checkout and in a cached Git
repository at its exact revision.
Verify sibling-schema discovery, a cross-folder reference and backlink, a source
permalink, a second revision, and a missing blob.
[Git architecture](../../architecture/arch-git.md).

## Testing Strategy

- **Golden transcripts** over the fixture for every route and every record state, as the
  parity registry requires.
- **Invariant tests.** A bad record leaves other rows available.
  A schema-only edit revalidates affected records and preserves unrelated projections.
  Warm table pages perform no payload reads.
  Opening full detail performs at most one record read.
  After a complete refresh, the index agrees with a fresh build of the same tree.
- **Fault injection:** a cache directory that cannot be created, a build cancelled
  mid-pass, a file deleted between the walk and the read, a schema that changes during a
  build.
- **Browserless sessions** for the view states, over the exact production JavaScript.
- **The benchmark** is rerun before any bound changes.

### End-to-End Scale Acceptance

Use the GitHub Universe `kb/` revision pinned in the
[research brief](../../research/research-2026-11-26-softschema-collection-tables.md#real-collections)
as the primary real acceptance benchmark.
Run `metab` against the corpus and open its Table view.
For the first implementation, exercise folder offer, table discovery, schema, paged
rows, and navigation to a linked row and back.
Record cold start and a warm reopen.
The later scale phase must also meet the early-page, bounded-memory, partial-coverage,
and incremental-update criteria below.
Capture the corpus revision, scan policy, parser mode, cache state, and route timings.
Keep corpus contents out of the repository.
See the
[Universe projection and route measurements](../../../../explorations/softschema-projection/README.md)
for the eager baseline and the reference-first experiment.

| User action | Acceptance evidence |
| --- | --- |
| Open `people/` with an empty cache | `--show people` offers Table. Call `/api/plugin/softschema/collection` and `/api/plugin/table/tables` without waiting for the full scan. Observe the catalog and indexing status, then the first usable Person page. Reconcile final per-contract counts and problem paths against an eager scan under the same policy. |
| Browse and sort people | Use `/api/plugin/table/schema` and `/api/plugin/table/rows` with the returned contract ID and folder path. Project named columns, sort, filter, and follow the returned cursor. Compare the completed result with the eager ordering, including a stable tie-breaker. Repeat warm and record payload reads. |
| Open a linked organization | Follow an actual affiliation from a Person row to its Organization using the returned table and key. Read the target card and record. Follow a backlink using the rows route with `ref` and `via`. Verify nested field identity, source path, visible folder scope, and collection-wide link resolution. Inspect only the selected record for full detail. |
| Edit one linked record | On a disposable fixture, change a person’s ID, sort field, and organization in one edit. Repeat the rows, card, record, and filtered inbound-link queries against the newly published generation. Verify that the row moves, the old target loses its backlink, and the new target gains it. Count source reads and row updates to establish that only the changed record was read and its dependent facts were updated. Repeat after a worker restart to check the durable index. |
| Interrupt and resume a refresh | On a disposable corpus fixture, edit a record and schema, introduce a conflicting fallback schema, remove a target, and cancel midway. Check the normal table routes against a single generation during the refresh, then against a fresh build. Ambiguous, missing, stale, and partially covered targets remain distinguishable. |

Complement Universe with a generated wide tree exceeding the eager scan’s aggregate byte
or entry bound. Include mixed profiles, late JSON declarations, large Markdown bodies,
and cross-folder IDs.
Increase corpus size with the displayed page and worker budgets held fixed.
Report time to first reference and first usable page, time to complete coverage, source
bytes and payloads read, peak resident memory, SQLite size, and warm refresh cost.
The first page must arrive while unrelated records remain unmaterialized.
Subsequent pages, cards, and backlink queries must use the published projection.
Reserve `wait=1` for final equivalence checks so it cannot hide the cost of opening the
first page.

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
