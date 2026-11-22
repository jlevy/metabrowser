# Research: Annotated Collections, with Guided PR as the First

**Date:** 2026-11-22

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft.
A design proposal for one question: can Guided PR’s guide be the first
form of the collection format, so that a pull request and a repository file use one
format? Nothing here is built.
Every design statement is a proposal; code claims cite the file they come from.

## Overview

Yes, and the cost is small if it is paid before
[pull request 677](https://github.com/jlevy/metabrowser/pull/677) merges.

A Guided PR guide is already an annotated collection: ordered items, each a title, a
note, and one or more references to code, under a short summary.
The [collection documents brief](research-2026-11-20-collection-documents.md) describes
the same thing for reading lists and dashboards.
The two differ in where references resolve, not in what an item is.

- **One record and one contract,** `metabrowser.collection:Collection/v1`: an optional
  `comparison` pin, a `summary`, an `overview`, and ordered `items`, each a `title`, a
  `note`, and `references`. Later fields are optional additions, which are not breaks.
- **The carrier decides the scope.** A fence in a PR description resolves references
  against the pinned comparison; a repository file resolves them against the served
  tree.
- **Layouts are views of the record a route answers.** Guided PR’s step view is one;
  rows, a table, cards, and a board are others.
- **Phase 1 is a rename inside #677,** with no new behavior: the contract ID, the
  envelope key, and four field names.
  Every later phase ships alone.

## What Each Is Today

### Guided PR

Guided PR is open and unmerged on branch `claude/guided-pr-ready`, 223 commits behind
`main`; its files are cited as paths on that branch.

- **Carrier and envelope.** One top-level fenced block whose info string is `guided-pr`,
  in the raw PR description, found among MarkdownIt block tokens with inline parsing
  disabled, so a fence inside another fence is an example (`guided_pr.py` in
  `src/metabrowser/builtin_plugins/github/`, lines 44 and 114–135). It holds
  `softschema:` metadata, which must equal the contract, envelope `guide`, and status
  `enforced` exactly, and a `guide:` payload (lines 140–147).
- **Contract.** A SoftSchema `Contract` the plugin builds with the `pure-yaml` profile
  (lines 34–42), validated by `validate_artifact` on the parsed document (line 148),
  then by strict Pydantic models with `extra="forbid"` (lines 71–111). It is not in the
  artifact-contract registry; `tests/test_guided_pr.py` (line 71) compares the model
  with `guided-pr-v1.schema.yaml`.
- **Record.** `comparison {merge_base, head}`, `feature`, `architecture`, and `steps`,
  each a `title`, `commentary`, and `references`; a reference is a `path`, optionally
  with `side` (`old` or `new`) and an inclusive `start_line` and `end_line`.
- **Staleness and bounds.** `stale` when the pinned head or merge base differs from the
  cached record, or the catalog knows a newer head (lines 342–349). `MAX_STEPS`,
  `MAX_REFERENCES`, and `MAX_EXCERPT_BYTES` carry their measurements (lines 46–61);
  `MAX_BODY_BYTES` in `pull_record.py` bounds the description.
- **Route and view.** `GET /api/plugin/github/guided-pr?number=&step=` answers one step,
  its excerpts, and a `state` per reference (lines 247–281); `guided-pr.js` draws one
  step at a time. Its golden is `tests/golden/cli-github-guided-pr.tryscript.md`.
- **Standing.** `changelog.d/mb-yakh.md` calls the block “the new external format
  `metabrowser.github:GuidedPR/v1`”.

### The Collection Brief

The brief, its [design memo](research-2026-11-20-collection-documents-design.md), and
the [technical review](../reviews/review-2026-11-20-collection-documents-technical.md)
decide nothing but converge: a collection is ordered items, optionally grouped, each
with a subject and a note; faces normalize to one record that a route answers; the
smallest step is one built-in plugin, one route, rows before Recent’s R4 cards, a table
through `[[table_source]]`, and no core change; and rendering never fetches a URL.

| Collection brief | Guided PR v1 | Difference |
| --- | --- | --- |
| Collection | `guide` | None in kind |
| Item | step | Same: ordered, titled, annotated |
| Note | `commentary` | Same; plain text |
| Subject | `references` | Up to `MAX_REFERENCES` per item; a reading-list item usually has one |
| Group | none | Not needed to step through a PR |
| Pin | `comparison` | A repository file needs none |

## The Unified Model

Five terms, all proposals:

- **Collection:** the record.
  Ordered items under a summary, with an optional pin.
- **Item:** a title, a note, and one or more references.
- **Reference:** what an item points at, written as an author would (a path, a range,
  later a URL) and resolved by the route into a state and an address.
- **Carrier:** where the record is written.
  It sets the base for relative paths, the scope references resolve in, and the pins it
  admits.
- **Layout:** a view of the record the route answered.

Four rules keep it small:

1. **The record is the contract.** Every carrier holds the same YAML, or, for a Markdown
   face, normalizes to the same record.
   One reader per contract.
2. **Carriers add few rules.** A PR description requires `comparison`; a repository file
   refuses it until something resolves a comparison outside a pull request.
3. **Start strict, relax later.** A required field made optional and an added optional
   field are not breaks; a renamed or retyped one is
   ([Contracts](../specs/active/plan-2026-11-14-object-data-model-and-views.md#contracts)).
   So phase 1 keeps every v1 requirement and changes only names.
4. **Resolution belongs to the route.** Membership, order, groups, and each reference’s
   state are computed on the server, as Decision 18 and the parity rules require.

What stays with the PR use is resolution, not format: checking paths against the
comparison’s changed files, excerpt rows under `MAX_EXCERPT_BYTES`, and staleness
against the catalog.
`side` is format, valid only with `comparison`.

## Contract and Schema

### One Contract, Not a Family

**Option A, one contract** (recommended): `metabrowser.collection:Collection/v1`,
envelope key `collection`. A PR guide is a collection whose carrier requires a pin.
One schema and one example for agents to learn, and a PR description can carry a reading
list as easily as a code tour.

**Option B, a family:** keep `metabrowser.github:GuidedPR/v1` and add a collection
contract that shares a Pydantic item class.
SoftSchema compiles each model to a self-contained schema, so the sharing is in Python
only. B costs two contract IDs, two envelope keys, and two documents, and buys only
stating the PR’s requirements in the schema instead of the carrier.
Nothing in the record is PR-only: the pin is optional data and `side` a reference
detail. B is the fallback if a PR-only field appears.

**SoftSchema mechanics under A** (softschema 0.8.1, pinned in `pyproject.toml`):

- **Profile.** SoftSchema has two, `frontmatter-md` and `pure-yaml`
  (`softschema/models.py`). A fence body and a YAML file are both `pure-yaml`; Guided PR
  already validates a fence body by passing the parsed document.
- **Status.** `enforced`: an invalid record is refused with its location, as today.
  `permissive` buys nothing: per the review’s finding 6, it does not change validation
  in 0.8.1. Extra keys stay forbidden, so a misspelled field is reported.
- **Registry.** Stay out of `plugin_loader/artifact_contracts.py`, which admits only the
  `enforced` `pure-yaml` records the cache writes.
  The plugin builds its `Contract` and drift-checks its schema in a test, as Guided PR
  does; `config.yml` in `cache/contracts.py` is the precedent for a user-written format
  validated outside the registry.
- **Ownership.** In phase 1 the module stays in the GitHub plugin, its only user, under
  the final ID. In phase 2 it moves to a built-in `collection` plugin that the GitHub
  plugin imports, as `github/pull_manifest.py` (line 34) imports from the diff plugin.
  A module move is internal; the contract ID does not change.

### Fields

| Field | Phase 1 (v1 renamed) | Later, without a version change |
| --- | --- | --- |
| `comparison {merge_base, head}` | Required | Optional in the schema (phase 2) |
| `summary` (was `feature`) | Required prose | — |
| `overview` (was `architecture`) | Required prose | Optional (phase 2) |
| `items` (was `steps`) | 1 to `MAX_ITEMS` | — |
| `items[].title` | Required prose | — |
| `items[].note` (was `commentary`) | Required prose | Optional only if the Markdown face needs it |
| `items[].group` | — | Optional label (phase 2) |
| `items[].references` | 1 to `MAX_REFERENCES` | — |
| `references[]` | `{path, side?, start_line?, end_line?}` | A `{url}` form (phase 3) |

All text stays plain text, drawn as typed, as Guided PR’s user guide says today.

### Example: A Pull Request Guide

````markdown
```guided-pr
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  comparison:
    merge_base: "<full merge-base commit ID>"
    head: "<full PR head commit ID>"
  summary: Readers can keep using cached data while a refresh runs.
  overview: A request serves the last snapshot while a worker builds the next one.
  items:
    - title: Inspect the request path
      note: Does the request return the snapshot before the worker finishes?
      references:
        - {path: src/cache.py, side: new, start_line: 42, end_line: 51}
    - title: Read the user guide change
      note: Check that it describes the stale window the code allows.
      references:
        - {path: docs/cache.md}
```
````

The fence keeps its `guided-pr` info string, the carrier’s marker, which the tab hint
(`GUIDED_FENCE` in `pull-page.js`, line 255) and the server read.
The contract says what the YAML is.

### Example: A Reading List in the Repository

A file such as `docs/research/handbook-site.yaml` (phase 2; the URL item is phase 3):

```yaml
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  summary: Seven briefs on where the team handbook should live.
  items:
    - title: Docs site options
      note: The main brief. Start here.
      group: Main brief
      references:
        - {path: research-2026-11-19-docs-site-options.md}
    - title: Hosted docs platforms
      note: The pricing and export sections decide it.
      group: Platforms and generators
      references:
        - {path: research-2026-11-19-hosted-docs-platforms.md}
    - title: Starlight documentation
      note: The generator the main brief recommends.
      group: Platforms and generators
      references:
        - {url: "https://starlight.astro.build/"}
```

The item has the same shape in both.
A research pull request’s guide whose references are all file-only is this reading list
already, pinned to its comparison and drawn one item at a time, in phase 1.

### Compatibility Before and After #677 Merges

[Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code) asks
whether a consumer cannot update with the producer, or released data needs migrating.
Before #677 merges, neither holds: no release reads `GuidedPR/v1`, and the only guides
were written to test it.
So phase 1 renames in place, with no second reader and no alias for the old ID, which
[AGENTS.md](../../../AGENTS.md#compatibility-and-legacy-code) forbids as a speculative
layer anyway.

After a release, guides are user data in PR descriptions and the file-format answer
applies: version and fail fast, one reader.
An old guide is refused by name, as a wrong contract is today (`guided_pr.py`, line
147). Every push makes a guide stale, so a later break strands only open pull requests;
that lowers the cost of a mistake, not the reason to settle the names now.

## Faces and Detection

| Face | Detected by | Untrusted text | Git pin | Phase |
| --- | --- | --- | --- | --- |
| A fence in a PR description | A top-level `guided-pr` fence, found by the server in the raw body | Third-party text; the server parses source and the page inserts fields as text | Pinned by `comparison` | 1, exists |
| A YAML file | `yaml_has_key = "collection"` on `.yaml` and `.yml`, above the structured plugin’s priority 0 | No HTML is rendered | Classified on pins (`plugin_loader/classify.py`, lines 392–405) | 2 |
| A Markdown link list | `frontmatter_has_key = "collection"` above the Markdown plugin’s priority 0; items from a server parse | The Document tab renders inert; items come from the server, so a dropped checkbox costs nothing | Classified on pins (`classify.py`, lines 371–373) | 4 |
| Items in frontmatter | The same key | — | — | Not planned: GitHub shows nested YAML as a table in a cell |
| A fence in a repository Markdown file | No predicate sees a fence; the inert path keeps only `mermaid` (`DIAGRAM_LANGUAGE` in `inert_html.py` and `static/inert-html.js`) | — | — | Not planned |

**A server parse of source sidesteps the inert-path fence problem for data.** Guided PR
never reads rendered HTML, so the language the inert path drops does not matter to it.
A repository fence still lacks detection, since predicates read only frontmatter or a
YAML prefix, and dispatch, since nothing loads a collection plugin when a plain Markdown
document renders (review, finding 7). That is the embedding question, and it waits.

**The envelope key is the marker.** `collection` carries the payload and is what a
classifier matches. `yaml_value_prefix` cannot match the contract, since `softschema` is
a mapping, and `path_glob` matches only on the filesystem.

**A detection risk for large YAML files.** `yaml_has_key` parses at most
`_YAML_PREFIX_BYTES` of a file (`classify.py`, lines 61–65 and 185–200), so a longer
file is classified only if its truncated prefix still parses, which a block list cut at
a line usually does and a flow mapping cut mid-line does not.
Phase 2 tests a file past that size; if it fails, the choices are a smaller file bound,
a key-only prefix scan in core, or the frontmatter carrier, bounded by
`FRONTMATTER_MAX_BYTES`.

## References

One `references` list, whose entries gain kinds over time:

| Kind | Written as | Valid in | Resolves to | Phase |
| --- | --- | --- | --- | --- |
| A changed file | `{path}` | A PR description | `file`, `path_not_changed`, or `manifest_truncated`, with the Changes address | 1, exists |
| A diff range | `{path, side, start_line, end_line}` | A PR description | Excerpt rows, or `range_unavailable`, `diff_unavailable`, `excerpt_too_large` | 1, exists |
| A served file or folder | `{path}` | A repository file | `file`, `folder`, or `missing`, with its address; a path leaving the served root is refused | 2 |
| A line range in a served file | `{path, start_line, end_line}` | A repository file | Text excerpt rows | Later |
| An external page | `{url}` | Anywhere | `external`; `https` only, never fetched, labeled by the item’s title | 3 |
| An object | `{object: {type, id}}` | Where the type has a route | The type’s address | After the object model |

**Paths are relative to the carrier’s base,** as a Markdown link is: the collection
file’s directory, or the repository root for a PR description, which has no directory.
One rule covers both, and the Markdown face inherits it; moving a collection changes its
paths, as moving a Markdown file does.
The normalized-path check `GuideReference` makes through `format_pull_href`
(`guided_pr.py`, line 88; `view_routes.py`, line 216) becomes a format rule, and each
carrier builds its own address.

**The route answers each reference** as the authored fields plus `state` and `href`,
with `rows` for an excerpt: the shape `_references` returns now (lines 247–281). When
the object model lands, the answer adds an `object` reference, so authors keep writing
paths and views receive references.
A PR reference is then a nested `changed-file` whose `parent` is the pull request
([Nesting, References, and Sub-Objects](../specs/active/plan-2026-11-14-object-data-model-and-views.md#nesting-references-and-sub-objects)),
with the range as a sub-object; a repository reference is a `file` or `folder`. A URL
stays a field, the proposed `web_url`, since a `url` type breaks the header’s meaning of
`href` (review, finding 5). An item is a nested object with references, after the Recent
plan’s `update` and its `subject`
([Contracts](../specs/active/plan-2026-11-18-recent-tab-updates-and-events.md#contracts));
its `id` is its position until something needs more.

## Pinning and Staleness

- **With `comparison`,** references resolve against that comparison, and the record is
  `stale` when the pull request has moved, as today.
  A PR description needs a pin because it is not versioned with the code it describes.
- **Without a pin,** a repository collection is versioned with what it references, so it
  is never stale: on a Git pin it reads that revision’s targets, and a missing target is
  a reference state. An open page refetches on `file.changed` through `mb.watchFile`.
- **Not proposed:** a `revision` pin for a repository file, until someone needs a
  collection about a past state.

## Layouts and Ownership

| Layout | Draws | Owner | Phase | Core change |
| --- | --- | --- | --- | --- |
| Steps | One item at a time with excerpts | GitHub plugin, `guided-pr.js` | 1, exists | None |
| Rows | Every item, a heading where `group` changes | `collection` plugin | 2 | None |
| Table | Items as records | `collection` plugin’s `[[table_source]]`, `requires = ["table"]` | 2 | None |
| Source | The file | `collection` plugin | 2 | None |
| Cards | A grid of the `card` frame | `collection` plugin | After [R4](../specs/active/plan-2026-11-18-recent-tab-updates-and-events.md#r4-later-each-alone) | The frame, built there |
| Steps for any collection | The step view over a repository file | `createGuideNavigation` moves to the `collection` plugin’s exports | Later | None |
| Board | Lanes by `group`, read-only | `collection` plugin | Later | View state for several lists ([Decision 17](../specs/active/plan-2026-11-14-object-data-model-and-views.md#decision-17-composing-a-page-of-several-lists)) |

Rows come before cards because a plugin-drawn card before R4 is the drift
[Decision 11](../specs/active/plan-2026-11-14-object-data-model-and-views.md#decision-11-the-set-of-shapes)
rules out. Lanes come from `group`, so one file is a list, a table, and a board with no
view configuration in the record.
The `collection` kind binds its own views, so a YAML file with an unrelated top-level
`collection` key would lose its Tree; the kind can offer the structured plugin’s tree
through its exports, as the `agents` plugin requires `structured`. No core change is
needed through phase 3.

## Parity and Bounds

### Parity

- **Phase 1.** The `guided-pr` route keeps its parity rows; its goldens
  (`cli-github-guided-pr.tryscript.md` and `cli-ui-github-guided-pr.tryscript.md` on the
  #677 branch) change only in field names.
- **Phase 2.** `GET /api/plugin/collection/record?path=` answers the normalized record
  and each reference’s state, with an `--api` golden covering groups, a file, a folder,
  a missing target, a path escape, a file past its bound, invalid YAML, and a wrong
  contract. A `metab --show` golden shows `kind: collection`; the table routes, a
  browserless session over the rows layout, parity rows, the
  [map](../architecture/arch-views-models-routes.md), and a changelog fragment land with
  it.
- **Later.** The Markdown face gets a golden of the same record from link-list input,
  which pins that both faces normalize alike.

### Bounds

- **`MAX_STEPS` becomes `MAX_ITEMS`,** keeping its measurement of parse cost per step
  (`guided_pr.py`, lines 49–57). The parse is the same for every carrier, so it
  transfers; a rows layout that wants more measures first.
- **`MAX_REFERENCES`** was set by a comparison’s per-step hydration, matching
  `INITIAL_PULL_FILES` (lines 46–48). A repository reference costs a stat, so it stays
  one format bound.
- **`MAX_EXCERPT_BYTES`** stays with the PR carrier’s excerpts.
- **A repository file is read up to `MAX_BODY_BYTES`,** because the parse measurement
  already covers text of that size (lines 53–55); a larger bound needs its own.
- **The parse cache** (`_READS`, lines 168–192) keys a PR by record revision; a file
  keys by content generation, as table sources do.
- **Card metadata** read from targets, when cards arrive, gets its own documents, bytes,
  and time budget, after the transclusion budget the review names.

## Incremental Path

**Phase 1, in #677 before it merges.** A rename, with no new behavior:

1. Contract `metabrowser.collection:Collection/v1`, envelope `collection`, schema file
   `collection-v1.schema.yaml`, still in the GitHub plugin.
2. `feature`, `architecture`, `steps`, and `commentary` become `summary`, `overview`,
   `items`, and `note`; `MAX_STEPS` becomes `MAX_ITEMS`. Every requirement stays.
3. `guided_pr.py` splits into the format (models, `parse_collection` of a parsed
   document, format bounds, the path rule) and the PR carrier (fence extraction, the
   comparison check, excerpts, the parse cache).
4. The route’s record fields, the `guided-pr.js` typedefs, tests, goldens,
   `docs/reviewing-pull-requests.md`, the architecture section, and `mb-yakh.md` follow.
   The route, its `step` parameter, the fence info string, and the tab stay.

**Phase 2, collection files.** A built-in `collection` plugin owns the format module, a
`collection` kind for YAML files, the record route, Rows, Table, and Source.
`comparison` and `overview` become optional in the schema; `group` is added.

**Phase 3, URL references.** `{url}`, `https` only, never fetched, opened as the inert
path opens an external link.
A PR guide can then cite a design document or an issue.

**Phase 4, the Markdown face.** A frontmatter-marked Markdown file whose headings are
groups and whose link items are items, parsed on the server by the KPress core in
`diff/markdown_projection.py` under bounds measured for link lists; a checkbox maps to
an optional, read-only `done`.

**Later, each alone.** Cards after R4; steps over repository files; line excerpts from
served files; object references; a read-only board; and a Documents view over a folder
or a pull request’s changed Markdown, from the same route internals with an implicit
member list.

## What Not to Do

- No second reader, alias, or migration for `GuidedPR/v1`.
- No `pin` union, `views:` list, layout setting, `from:` query, or filter language.
- No alternate spellings: one way to write a reference, no string shorthand.
- No URL fetches or unfurl cache.
- No fences in repository Markdown, and no inert allowlist change, before embedding is
  decided on its own.
- No core change: no registry admission, no `document` facet on `file`, no new shape.
- No cards before R4, and no write-back before structural edits exist.
- No contract family unless a PR-only field appears.
- No generalizing the `guided-pr` route into a collection route; each carrier keeps its
  own.

## Open Questions for the Owner

1. **The name.** `collection` is the object model’s word and the key a classifier
   matches; it is generic and may collide with other tools’ YAML. Is it what users see?
2. **The header.** SoftSchema treats `envelope` and `status` as optional
   (`softschema/models.py`). Should the header shrink to `softschema: {contract: …}`,
   which keeps the version that fail-fast needs?
   Whether `validate_artifact` then warns is unverified.
3. **The fence name.** Should a PR description also accept a `collection` fence, so one
   word appears everywhere, or does `guided-pr` say more to a PR author?
4. **`summary` and `overview`.** Do the generic names lose the prompt `feature` and
   `architecture` give an author, or can the user guide carry it?
5. **Which repository face first:** the YAML file (identical bytes, the detection risk)
   or the Markdown link list (better on GitHub, a new parser)?
6. **Other layouts for a pull request.** Should the Guided tab offer Rows beside Steps?

## References

- Guided PR on branch `claude/guided-pr-ready`: `guided_pr.py`,
  `guided-pr-v1.schema.yaml`, `guided-pr.js`, `pull-page.js`, and `manifest.toml` in
  `src/metabrowser/builtin_plugins/github/`; `docs/reviewing-pull-requests.md`;
  `docs/project/architecture/arch-github-pull-requests.md`; `tests/test_guided_pr.py`;
  `tests/golden/cli-github-guided-pr.tryscript.md`; `changelog.d/mb-yakh.md`
- Pull requests [677](https://github.com/jlevy/metabrowser/pull/677) (Guided PR),
  [679](https://github.com/jlevy/metabrowser/pull/679) (collection documents), and
  [570](https://github.com/jlevy/metabrowser/pull/570) (object-model plans)
- [Collection documents](research-2026-11-20-collection-documents.md),
  [design memo](research-2026-11-20-collection-documents-design.md),
  [prior art](research-2026-11-20-collection-formats-prior-art.md),
  [reading list](research-2026-11-20-collection-documents-reading-list.md), and
  [technical review](../reviews/review-2026-11-20-collection-documents-technical.md)
- [Object Data Model and Views](../specs/active/plan-2026-11-14-object-data-model-and-views.md),
  [Plugin Authoring](../specs/active/plan-2026-11-18-plugin-authoring-objects-views.md),
  [View Model and View State](../specs/active/plan-2026-11-18-view-model-and-view-state.md),
  and [The Recent Tab](../specs/active/plan-2026-11-18-recent-tab-updates-and-events.md)
- [Table Sources](../../plugins.md#table-sources),
  [Plugin System](../architecture/arch-plugin-system.md),
  [Parity Registry](../architecture/arch-parity-registry.md), and
  [Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code)
- On `main`, under `src/metabrowser/`: `plugin_loader/classify.py`,
  `plugin_loader/artifact_contracts.py`, `cache/contracts.py`, `inert_html.py`,
  `static/inert-html.js`, `view_routes.py`, and `diff/markdown_projection.py`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
