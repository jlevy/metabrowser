# Research: Tables Over Folders of SoftSchema Records

**Date:** 2026-11-26

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete.
Informs
[the SoftSchema collection tables plan](../specs/active/plan-2026-11-26-softschema-collection-tables.md).

## Overview

A knowledge base kept as files is a tree of SoftSchema artifacts: Markdown with YAML
frontmatter, or pure YAML, each naming the contract its payload follows and usually
pointing at a compiled JSON Schema kept somewhere else in the tree.
Paraverse loads two such trees into FalkorDB and browses them as linked tables.
Metabrowser shows each file on its own: a person record opens as a Markdown document,
and nothing shows the 577 people as one table.

The tabular data plan
([plan-2026-11-19-tabular-data-and-live-sqlite.md](../specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md))
left this as an open question: “Should a directory of SoftSchema records sharing one
contract open as one table, as a knowledge base’s folders would?
The protocol supports it; the open question is the kind rule and the cost of reading
every file.”
This brief answers the cost question with measurements, and maps the format,
the real collections, Paraverse’s browser, and Metabrowser’s table machinery onto the
decisions a plugin has to make.

## Questions to Answer

1. What does a SoftSchema artifact promise a reader, and what does it leave to the host?
2. How are real collections laid out: where do schemas live, how do records map to
   folders, and how do records refer to each other?
3. What does reading and validating a whole collection cost, with the readers
   Metabrowser already ships?
4. Which parts of Paraverse’s knowledge base browser are generic, and which are specific
   to its conference data?
5. What in Metabrowser can a collection table reuse, and what is missing?
6. How can a table stay useful when some records are malformed, unbound, or invalid?

## Scope

Included: the SoftSchema 0.8.1 spec and Python package; the GitHub Universe and Patch
the Conference knowledge bases; Metabrowser’s own experiment records; Paraverse’s `db/`
browser; Metabrowser’s plugin, table, and cache machinery.

Excluded: editing records, the FalkorDB graph itself, full-text search across a
collection, and a graph drawing of references.
A single artifact that holds a list of items (`kb/faq.yaml`, `kb/media.yaml`) is already
the structured plugin’s record-list table and is not a collection.

## Findings

### SoftSchema in Brief

An artifact is a file with a `softschema:` metadata block and a payload
([spec](https://github.com/jlevy/softschema/blob/main/docs/softschema-spec.md)):

```yaml
softschema:
  contract: paraverse.conference:Person/v2   # what the payload is
  schema: ../_schemas/person.schema.yaml      # where its compiled schema is (optional)
  envelope: person                            # which top-level key holds it (optional)
  status: enforced                            # soft | permissive | enforced (optional)
person:
  id: person:aaron-reich
  name: Aaron Reich
```

- **Two profiles.** `frontmatter-md` puts the metadata and payload in the frontmatter,
  with a reader-facing Markdown body that is never a source of values.
  `pure-yaml` is the whole document.
  A `*.yaml` or `*.yml` name means pure YAML; a file that opens a `---` fence is
  frontmatter Markdown.
- **Envelope.** The payload is the value of one top-level key.
  Other top-level keys (`title:`) are the host’s and SoftSchema ignores them.
  With no `envelope:` and one non-`softschema` key, that key is the envelope; with
  several, the artifact is ambiguous.
- **Schema binding precedence.** A caller’s explicit schema, then a host registry, then
  the document’s own `softschema.schema`, then none.
  The document’s pointer is relative to the document.
  The reference CLI refuses a pointer that escapes both the document’s directory and the
  working directory.
- **Status is not evidence.** `enforced` means undeclared properties fail when a
  structural schema is bound; it does not mean a check ran.
  Results report `execution` per layer (`not_run`, `completed`, `errored`).
- **Compiled schemas** are JSON Schema 2020-12, written as YAML, with a root
  `x-softschema: {contract, schema_sha256}` block naming the contract they compile.
  So a schema can be found by contract as well as by path.
  Per-field `x-softschema` blocks may carry `group`, `owner`, `tier`, `instruction`,
  `examples`, and `aliases`.
- **Portable YAML.** Implicit dates and timestamps stay strings, as do `yes` and `on`;
  duplicate keys, anchors, tags, and non-finite numbers are refused.
  PyYAML reads YAML 1.1, so it disagrees on `yes`, `on`, `0o17`, and sexagesimal
  numbers, and accepts duplicate keys.
- **Repair and conform exist and can run without writing.** `repair_yaml_text` quotes
  scalars that broke a parse and keeps the repair only if the result is portable;
  `conform_artifact(..., write=False)` coerces scalars to the string type a schema
  declares (a brand named `1850`).
- **Library surface used here:** `read_frontmatter_doc`, `read_yaml_doc`,
  `parse_schema_metadata` (fields `contract_id`, `schema_ref`, `envelope`, `status`),
  `validate_artifact` (which needs a `Contract`; with none it answers
  `contract_unknown`), `validate_values(values, schema=, status=)`, and `SchemaView`
  (fields by JSON Pointer with type, enum, required, description, and `x-softschema`).
  `SchemaView` does not report list-ness, titles, `pattern`, `format`, or the `$def` an
  array’s items name, which a column model needs.

### Real Collections

Three collections were surveyed: GitHub Universe (`jlevy/universe2026-md` at `a823679`),
Patch the Conference (`jlevy/ptc2026-md` at `967e668`), and this repository’s
`explorations/performance-loop/experiments/`.

| Collection | Artifacts | Contracts | Schema location | Profiles |
| --- | ---: | ---: | --- | --- |
| Universe `kb/` | 4,977 | 18 | `kb/_schemas/`, pointed at as `../_schemas/<kind>.schema.yaml` (or deeper) | 1,420 Markdown, 3,557 YAML |
| Patch the Conference `kb/` | 132 | 9 (18 schemas) | `kb/_schemas/` | 33 Markdown, 99 YAML |
| Metabrowser experiments | 72 of 156 files | 1 | `experiment.schema.yaml` beside the records | Markdown |

- **One contract per subtree, not per folder.** `people/` holds 577 Person records.
  `accounts/` holds 1,052 SocialAccount records across `x/`, `linkedin/in/`,
  `linkedin/company/`, `bluesky/`, `mastodon/`, `youtube/c/`, and `other/<host>/...`.
  `repositories/` is 1,155 Repository records in 372 owner folders.
  `packages/go/github.com/...` nests seven deep.
  A table is a contract within a subtree, whatever the folders under it.
- **Schemas usually live outside the folder a reader opens.** Opening `kb/people/` needs
  `kb/_schemas/person.schema.yaml`; opening `kb/accounts/x/` needs a schema three levels
  up. The experiments keep theirs beside the records.
- **Every artifact in these trees carries all four metadata keys**, and every one is
  `status: enforced`. A collection that names only `contract` needs the contract to
  schema index the root `x-softschema.contract` makes possible.
- **Mixed folders are normal.** The experiments folder holds protocols (`.txt`), samples
  (`.jsonl`), and the schema beside its 72 records.
  `kb/` holds `README.md` (no frontmatter), `faq.yaml` and `media.yaml` (one artifact
  each), and the derived `_graph/` and `_search/` exports.
- **Versions differ between datasets.** Universe is `paraverse.conference:*/v2`; Patch
  the Conference is `*/v1` with two additive extensions.
  Paraverse merges them (`merge_kind_schemas` in `db/src/paraverse_graph/schemas.py`).
- **Records refer to each other by typed IDs.** `person:aaron-reich`, `org:avanade`,
  `session:2025/bld1566m`, `gh:asreic`. The compiled schemas carry 87 reference patterns
  such as `^(gh|acct):[a-z0-9]...`, whose alternation names the ID prefixes a field may
  hold. Every record’s own ID is in its payload’s `id`.
- **Field sizes vary widely.** Median artifact sizes run from about 0.6 KB (packages) to
  5.5 KB (organizations); the largest organization is 96 KB and the media index 433 KB.
  A person’s `bio` and a session’s `abstract` are paragraphs.
- **Coverage is uneven.** `_graph/coverage.json` reports, per kind, the share of records
  filling each field: every session has `title` and `slots`, 86% have `speakers`, 3%
  have `related`. A table’s default columns should come from coverage rather than from a
  hand-kept list.
- **The Markdown bodies restate the payload** for readers (a session’s time, room,
  speakers, and topics), so the record view can show the body as a document beside the
  fields without parsing it.

### Cost of Reading a Collection

Measured on 2026-11-26 in a 4-processor Linux container (Python 3.13.18, PyYAML 6.0.3
with its C loader, ruamel.yaml 0.19.1 without `ruamel.yaml.clib`, jsonschema 4.26.0,
SoftSchema 0.8.1), over Universe’s `kb/` with `_`-prefixed folders skipped: 4,978 files,
15.7 MB, 4,977 artifacts.
Times are single warm runs; rows marked with a count ran on the first 1,000 files, whose
mix of kinds differs from the whole.
The scripts are not committed; the plan adds a benchmark that repeats them.

| Work | Per file | Whole tree |
| --- | ---: | ---: |
| Walk and `stat` every file, and hash the stats | 3 µs | 15 ms |
| Read up to the closing fence, without parsing | 9 µs | 47 ms |
| PyYAML C loader, timestamps kept as strings | 279 µs | 1.4 s |
| jsonschema, one validator compiled per schema, on PyYAML’s payloads | 479 µs | 2.4 s |
| PyYAML C plus `validate_values` (1,000 files) | 2.4 ms | about 12 s |
| SoftSchema `read_frontmatter_doc` / `read_yaml_doc` | 6.8 ms | 34 s |
| Metabrowser `load_frontmatter_yaml` (1,000 files) | 9.1 ms | about 45 s |
| SoftSchema read plus `validate_artifact` (1,000 files) | 17.7 ms | about 88 s |

- **The pinned SoftSchema is the slow one.** Metabrowser pins 0.8.1 and does not install
  `ruamel.yaml.clib`, so every reader here ran ruamel’s pure-Python parser.
  SoftSchema 0.9.0 (2026-10-26) reads C-first: it hands libyaml every text on which
  libyaml was shown to read exactly as pure ruamel, 4 to 7 times faster, and reads
  strict JSON with the standard `json` module, over 10 times faster again
  ([guide, Performance](https://github.com/jlevy/softschema/blob/main/docs/softschema-guide.md#performance)).
  At 4 to 7 times, SoftSchema’s own reader would take about 1 to 1.7 ms per record here,
  5 to 8 s for the whole tree, with portable results.
  This was not measured: installing `ruamel.yaml.clib` is a third-party dependency
  change that needs the supply-chain review first.
- **So no second reader is needed.** The PyYAML C loader is faster again, but it reads
  YAML 1.1 and would need its own verification pass; once SoftSchema reads C-first, one
  exact reader in a background build is fast enough.
- **Validation through `validate_values` is about five times the bare validator.** A
  profile of 300 calls put 1.6 s of 2.1 s in jsonschema’s `iter_errors` and 0.6 s in
  building four validators (the cache holds them after that).
- **Freshness is cheap.** A `stat` walk of the whole tree is 15 ms, so a request can
  learn whether anything changed without trusting a watcher.
- **A cache makes the cost one-time.** After the first build, a changed file costs one
  parse and one validation, a changed schema costs revalidating its records from parsed
  payloads already held, and an unchanged tree costs the stat walk.

### Paraverse’s Browser

Paraverse’s `db/` package serves a read-only knowledge base browser from FalkorDB
([kb browser plan](https://github.com/jlevy/paraverse/blob/main/docs/project/specs/done/plan-2026-10-24-kb-browser.md)).
Its goal was “one generic, schema-driven model … A new kind or field appears with no
front-end change.” It nearly meets it; the exceptions are what a Metabrowser plugin has
to replace with data.

Generic, and worth carrying over:

- **`describe_fields`** (`schemas.py`): a field list from a compiled schema, with title,
  description, JSON type, list-ness, required, enum, `format: url` from a URL pattern,
  the `$def` a nested value names, and the kinds a typed-ID pattern allows.
  Nullable `anyOf` branches collapse to their value branch.
  Order: `id`, then required, then the rest, each alphabetical, since compiled schemas
  lose declaration order.
- **`merge_kind_schemas`:** a union of two datasets’ versions of one contract, keeping
  only shared requirements and both sides’ enum values.
- **Cells by type** (`table.js`, `values.js`): text, numbers, booleans as badges, URLs
  as links, images as thumbnails, references as chips, nested values as a count and a
  preview, relationship columns as three chips and “+N”.
- **The record view** (`record.js`): fields in schema order, nested objects as a
  definition list, lists of objects as a sub-table over their `$def`’s fields, long text
  as Markdown, outgoing and incoming references by type, sources, and the raw payload.
- **The overview:** kinds grouped, with counts, and a review table of data-quality
  checks whose rows link to records.

Specific to the conference data, and so not portable as written:

- **`PREFIX_KINDS`**, a hand-kept map from ID prefix (`gh`, `acct`, `org`) to kind, in
  Python and again in `values.js`.
- **`NESTED_KINDS`**: `day` lives in `event`, `term` in `facet`.
- **Default columns, kind groups, and kind colors** per kind.
- **Review checks** are Cypher queries over the graph.
- **The graph itself** is the source of relationships; the browser reads nothing from
  `kb/`.

### Metabrowser Today

- **A table plugin already exists and was modeled on Paraverse’s browser**
  (`builtin_plugins/table/table-view.js`, header: “the record opens in place of the grid
  … as paraverse’s browser opens one”). It has search, filter chips, a column picker, a
  windowed grid, a record view, hover cards, references and back-references, and its
  state in the address.
- **The `TableSource` protocol** (`src/metabrowser/table_source.py`) answers
  `generation`, `tables`, `schema`, `rows`, `record`, and `card` for one source with any
  number of tables. `TableField` has `type`, `list`, `enum`, `format`, and a `FieldRef`
  (table, fields, to); `TableSchema` has `references` and `referenced_by`; `TableQuery`
  has a `ref=<table>:<key>` filter.
  This is Paraverse’s relationship model, typed.
- **A source is opened from one file.** `TableHandle` is one file’s content reference,
  `open_table_source` classifies a file to find its adapter, and `[[table_source]]`
  names a kind. No kind matches a directory: the folder is a core kind, assigned by the
  server.
- **A folder can be offered a view.** `[[view]] kind = "folder"` with
  `offer = "module:fn"` adds a tab whose predicate “reads no more than a few directory
  entries”; an offered `default = true` view becomes the folder’s default.
  The agents plugin is the precedent (`agents/homes.py`).
- **The fsqlite plugin is a folder read as tables**, but through a marker file:
  `folder_marker = "fsqlite.json"` badges the folder, and opening the marker opens the
  store as a container whose children are its tables.
- **Many-file reads have a precedent.** The agents catalog (`agents/catalog.py`) runs a
  fast `stat` pass and a bounded summary pass on a single-flight worker thread, caches
  summaries in `plugin_cache_directory`, keeps working in memory when the cache is
  unavailable, and gives `metab --api` a `complete()` that waits, bounded.
- **`memory.py`** in the table plugin is an in-memory sort, filter, and cursor engine,
  for built-in sources only.
- **SoftSchema is already a dependency**, used for Metabrowser’s own trusted contracts
  (`plugin_loader/artifact_contracts.py`, `cache/contracts.py`,
  `github/guided_review.py`). Nothing validates an arbitrary file against the schema it
  names. Importing `metabrowser` must not load `softschema` or `jsonschema`
  (`tests/test_plugin_public_api.py`).
- **Kind predicates** include `frontmatter_has_key` and `yaml_has_key`, but none reads a
  nested value such as `softschema.contract`.
- **Parity:** a new route needs a covered row and a `metab --api` golden; a new kind a
  `--show` golden; a new view an interaction or paint-exempt row
  ([parity registry](../architecture/arch-parity-registry.md)).

## Key Insights

- **The UI is mostly built; the source is not.** Metabrowser’s table view already does
  what Paraverse’s table and record views do, with references in its protocol.
  The work is a source that reads a tree, and a record view that knows SoftSchema’s
  nested shapes.
- **The expensive part is parsing, and it is one-time.** A cold build of the largest
  tree surveyed cost about 90 s with the pinned portable reader and `validate_artifact`,
  and should cost seconds with 0.9.1’s C-first reader; a warm open costs a 15 ms stat
  walk. The design is a cache with incremental rebuilds, not a faster request path.
- **The machinery is SoftSchema’s, not Metabrowser’s.** Walking a tree for artifacts,
  binding each to a schema by pointer or by contract, validating in batch with prepared
  validators, repairing in memory, describing fields, and keeping all of it current by
  stat are format concerns.
  Paraverse already reimplements part of it (`kb.py` reads artifacts with its own
  loader; `schemas.py` describes fields), and the Universe pipeline validates its tree
  with its own loop. In SoftSchema, each consumer gets one implementation, and
  Metabrowser gets each improvement, faster parsing included, by upgrading.
- **ID prefixes can be learned instead of listed.** Each table’s `id` values show its
  prefix (every Person ID starts `person:`), and each reference pattern’s alternation
  names prefixes. Joining the two replaces `PREFIX_KINDS` with data, and a value that
  equals a known ID can link even without a pattern.
- **A table is a contract, not a folder.** Grouping by contract within the opened
  subtree gives `accounts/` one SocialAccount table and `kb/` eighteen tables, which is
  what the `tables()` method already models.
- **A bad record must cost a row, not the table.** Every failure the format defines has
  a narrower blast radius than the collection: a parse error loses one row’s values, a
  missing schema loses one table’s types, a validation error loses nothing but a
  verdict.

## Options Considered

### Finding a Record’s Schema

**Option A: the record’s own pointer only.** Resolve `softschema.schema` against the
record’s directory, inside the served root.

- Pro: exactly what the CLI does, and every surveyed record has one.
- Con: a contract-only record gets no schema; a pointer outside the served root fails.

**Option B: the pointer, then a contract index.** As A, and when a record has no usable
pointer, look its contract up in an index of the compiled schemas found under the
collection root (any `*.schema.yaml` or `*.schema.json` whose root `x-softschema` names
a contract).

- Pro: covers contract-only records and the conventional `_schemas/` folder without a
  configuration file.
- Con: two schemas claiming one contract need a rule (prefer the one most records point
  at, and say so).

**Option C: a collection file.** A file at the collection root names the schema folders,
contract groupings, and display hints.

- Pro: explicit, and a home for hints such as default columns.
- Con: every existing collection would need one; none has it today.

### Choosing the Collection Root

**Option A: the opened folder.** Index exactly the subtree the reader opened.

- Pro: simple, and the cost follows the folder.
- Con: opening `kb/people/` loses references to organizations and sessions, which live
  in sibling folders.

**Option B: the nearest ancestor that holds the schemas.** Walk up from the opened
folder, within the served root, to the folder whose subtree holds the schemas the
records point at, index that, and show the opened folder as a path filter on it.

- Pro: references resolve from any subfolder, and one cache serves every subfolder.
- Con: opening a small subfolder of a large tree pays for the whole tree once.

### Reading Values

**Option A: SoftSchema’s portable reader, C-first.** One reader, exact verdicts; upgrade
to 0.9.1 and add `ruamel.yaml.clib`.

**Option B: PyYAML’s C loader, then portable verification in the background.** Rows in
about 1.4 s, verdicts later; two readers whose disagreements must be marked.
Only worth it if Option A, measured, is still too slow.

**Option C: Metabrowser’s bounded loader.** The slowest measured (9.1 ms per file), and
it adds nothing the portable reader does not.

### Where the Collection Logic Lives

**Option A: in the Metabrowser plugin.** Fastest to start; every other consumer keeps
its own copy, and Metabrowser carries format logic AGENTS.md keeps out of core.

**Option B: in SoftSchema, used by the plugin.** A collection API (scan, bind, validate,
repair in memory, describe, refresh) and a `softschema` command over a folder.
The plugin keeps the cache location, the worker thread, the table mapping, references,
and the views. SoftSchema releases Python and TypeScript together, so its parity process
decides whether the API lands in both at once.

### Eliminated Options

- **Load the tree into a database server.** Paraverse’s FalkorDB load answers graph
  queries Metabrowser does not need, and adds a service.
- **A marker file to open a collection,** as fsqlite does.
  Existing collections have no marker, and the folder view offer reaches the same place
  without one.
- **Parse records on each request.** The cheapest measured cold read is seconds.
- **Parse the Markdown body for values.** The spec forbids it, and the payload holds
  everything the body restates.

## Recommendations

- A built-in `softschema` plugin whose Table view is offered on a folder, and whose
  source is the collection rooted at the nearest ancestor that holds the records’
  schemas, one table per contract.
- Upgrade to SoftSchema 0.9.1 with `ruamel.yaml.clib`, after the supply-chain review,
  and measure the reader before designing around its cost.
- Put the collection logic in SoftSchema: scanning a tree, binding schemas by the
  record’s pointer and then by a contract index of compiled schemas under the root,
  batch validation, in-memory repair, the field model, and incremental refresh by stat
  and schema digest.
- A cache in the plugin’s cache directory, built by a background worker as the agents
  catalog is, holding what SoftSchema’s collection API returns.
- Graceful degradation as a rule of the source: every record that can be read is a row,
  every row says its state, and no record’s failure reaches another.
- References from data: learned ID prefixes joined with reference patterns, mapped onto
  the protocol’s `FieldRef`.
- A record view that draws nested `$defs` shapes as Paraverse’s does, and an overview of
  tables, counts, coverage, and problems.

## Next Steps

- [ ] Write the plan spec.
- [ ] Decide the open choices in the plan with the maintainer: the default view and the
  collection root.
- [ ] Measure SoftSchema 0.9.1’s reader with `ruamel.yaml.clib` after the supply-chain
  review.
- [ ] Plan the collection API in SoftSchema’s repository.

## Methodology

Read the SoftSchema README, spec, and guide at `c84456d`, and its installed 0.8.1
package. Surveyed the three collections with a script that walked each tree and grouped
files by folder, extension, contract, and size.
Read Paraverse’s `db/` package and its browser plan.
A delegated survey mapped Metabrowser’s plugin loader, table plugin, and parity rules,
and the cited files were read to confirm it.
Timing scripts ran each reader over the same file list in one process.

## References

- [SoftSchema](https://github.com/jlevy/softschema): README, spec, guide (official
  documentation and source)
- [universe2026-md](https://github.com/jlevy/universe2026-md) and
  [ptc2026-md](https://github.com/jlevy/ptc2026-md): the surveyed knowledge bases
- [Paraverse](https://github.com/jlevy/paraverse): `db/src/paraverse_graph/` and
  `docs/project/specs/done/plan-2026-10-24-kb-browser.md`
- [Tabular data plan](../specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md),
  Open Questions
- [Object data model plan](../specs/active/plan-2026-11-14-object-data-model-and-views.md)
- [Plugin System](../architecture/arch-plugin-system.md) and
  [Parity Registry](../architecture/arch-parity-registry.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
