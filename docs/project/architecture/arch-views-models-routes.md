# Views, Models, and Routes

**Status:** Implemented, except where a row says otherwise.

The map of what Metabrowser shows, what it shows it from, and how each thing is
addressed. Every other architecture document explains one of these in depth; this one is
the index that says how they fit together, and the place to look first when adding a
kind, a view, a data format, or a route.

## The four layers

A selection travels the same four layers no matter what it is:

```text
route  ──►  kind  ──►  model  ──►  view
what kind   what the   the        how it
of thing    thing is   validated  is drawn
is selected            data
```

- **Route** names the address space and the thing within it.
  Owned by the shell; see
  [Browser URL Grammar](../../architecture.md#browser-url-grammar).
- **Kind** is the classification a plugin claims, declared in its `manifest.toml`
  `[[kind]]` block. One kind, many views.
- **Model** is the validated data a view receives.
  Simple kinds take the `/api/file` envelope; richer kinds have their own documented
  format with a schema and a conformance corpus.
- **View** is a registered renderer (`[[view]]` plus `mb.registerView`), shown as a tab.
  A kind’s `default = true` view is what a selection opens.

The layers are deliberately decoupled: a view never learns which source produced its
model, and a model never learns which route reached it.
That is what lets one diff renderer serve a patch file, a commit, and later a pull
request without knowing the difference.

## Kinds and their views

Built-in kinds, as registered by the manifests in `src/metabrowser/builtin_plugins/`:

| Kind | Matches | Views (default first) | Model |
| --- | --- | --- | --- |
| `folder` | Directories | Overview, Treemap | Folder envelope + [File Rollup Format](file-rollup-format/file-rollup-format.md) |
| `markdown` | `.md` | Document, Source | File envelope; KPress render |
| `text` | Text files | Source | File envelope |
| `structured` | `.json`, `.yaml`, `.yml` | Tree, Source | File envelope, parsed hook |
| `diff` | `.patch`, `.diff` | Diff | [File Diff Format](file-diff-format/file-diff-format.md) |
| `agent-log` | `.jsonl` sniffed as an agent log | Log, Charts, Raw JSON | File envelope, charts hook |
| `unknown-jsonl` | Other `.jsonl` | Log, Raw JSON | File envelope |
| `binary` | Non-text files | Bytes | Bounded byte-chunk hook |

Two kinds are also **containers** — folder-like entries whose children are addressable
(see [nav containers](arch-nav-containers.md)): `folder` (children are files and
folders) and `diff` (children are the files a patch changes).

### Shared Source rendering

`text`, `structured`, and `markdown` all expose raw source from the file envelope.
Generic text and structured views use the SDK’s shared Source renderer; Markdown keeps
its custom frontmatter split but follows the same language and size decisions.
A source view never embeds another kind’s renderer, because nondefault plugins mount on
demand and may not be loaded.

The server owns the logical-extension and basename grammar maps plus the syntax byte
bound and injects them with the file envelope settings.
A renderer emits exact escaped text and a host language class.
The shell enhances the mounted subtree after the renderer settles and after first paint,
whether the tab was initially visible or mounted later.
Diff views need tokens in their semantic line model rather than markup, so they call the
bounded SDK token service but use the same injected registry, prefetched grammars, and
palette. Diff intraline ranges follow the same ownership rule: they are browser-local
enrichment over exact line text, composed with syntax runs in the renderer and shared by
unified and split projections.
Neither enrichment extends File Diff Format v1.

The registry-to-vendored-grammar and registry-to-text-routing checks live in
`test_plugin_sdk_syntax_token_contracts` and
`test_syntax_language_extensions_are_always_browser_text`.

## Documented data formats

Formats with a schema, a conformance corpus, and implementations bound by it.
These are tool-neutral: nothing in a document references Metabrowser.

| Format | Describes | Authority | Implementations |
| --- | --- | --- | --- |
| [File Diff Format v1](file-diff-format/file-diff-format.md) | A change set between two snapshots | `data/file-diff-format/file-diff.schema.json` | `metabrowser.diff.format` (Pydantic), `builtin_plugins/diff/diff-model.js` |
| [File Rollup Format](file-rollup-format/file-rollup-format.md) | File classification and directory totals | `data/file-rollup-format/` | Python inventory, browser rollup projection |

Everything else travels as an envelope on `/api/*`, versioned with the shell and the
built-in plugins as one artifact — an internal contract, not a standard.
[Where diff documents come from](file-diff-format/diff-sources-and-anchoring.md) maps
the sources that produce them.

## Routes

### Browser routes: one per address space

| Route | Selects | Status |
| --- | --- | --- |
| `/view/<path>` | Content in the served tree; `/view/` is the root | Implemented |
| `/view/<container>/<inner>` | One entry inside a container file | Implemented |
| `/commit/<rev>` | A commit’s change set against its first parent | Implemented |
| `/commit/<rev>/<inner>` | One file’s diff inside that change set | Route parses; the panel restores the commit, not yet the file |
| `/compare/<base>..<head>[/<inner>]` | An explicit comparison (`...` for merge base) | Specified, not built |

The shape after the route is always `<container address>/<inner path>`, which is the
container contract written as a URL. The full grammar, including the `_mb_` query
reservation and its invariants, is in
[Browser URL Grammar](../../architecture.md#browser-url-grammar).

### Data routes

| Route | Serves |
| --- | --- |
| `/api/file` | The file or folder envelope: kind, views, content window |
| `/api/tree`, `/api/rollup`, `/api/recent` | Navigation: subtrees, rollups, the recency window. `/api/tree` also resolves the nav filter (`types`, `recency`, `min_size`, `include_ignored`), returning only subtrees that contain a match and folder aggregates rolled up from those matches |
| `/api/activity`, `/api/stream` | Live inventory and activity events |
| `/api/git/repo`, `/api/git/refs`, `/api/git/summary`, `/api/git/log`, `/api/git/commit/<rev>` | Read-only Git history for the Git panel; log pages use bounded, replayable server sessions, opaque page cursors, and versioned graph-boundary checkpoints. The boundary and its rules are in [Git and comparison sources](arch-git-and-comparison-sources.md) |
| `/api/kpress/render`, `/api/kpress/export` | Document rendering and export |
| `/api/plugin/<plugin>/<route>` | Plugin data hooks (`[[data_hook]]`) |
| `/raw` | Bounded raw bytes for embedded media |
| `/kpress-static/<path>`, `/static/<path>`, `/plugin-static/<plugin>/<path>` | Shell, renderer, and plugin assets |

Plugin hooks currently registered: `diff/document`, `diff/children`, `diff/comparison`,
`folder/*`, `binary/chunk`, `agent-log/charts`, `structured/parsed`.

## CLI parity

Every data surface the browser consumes is reachable from `metab` without a browser or a
listening port, and should be pinned by a golden transcript.
`--api` makes reachability true by construction; the remaining debt is coverage, and it
is listed here rather than left implicit.
`devtools/check_parity.py` fails the build when this table drifts from the registered
routes.

Status values: **covered** names the goldens that pin it and **exempt** gives the reason
it has no model to pin.
There is no third value: `check_parity.py` rejects a `gap` row outright, so a new route
arrives with a transcript or the build fails.

| Surface | Status | CLI | Golden or reason |
| --- | --- | --- | --- |
| `/api/file` | covered | `--show PATH`, `--api` | `cli-show.tryscript.md`, `cli-api.tryscript.md` |
| `/api/tree` | covered | `--walk`, `--api` | `cli-api.tryscript.md` |
| `/api/rollup` | covered | `--api` | `cli-api-nav.tryscript.md` |
| `/api/recent` | covered | `--api` | `cli-api-nav.tryscript.md` |
| `/api/activity` | covered | `--api` | `cli-api-nav.tryscript.md` |
| `/api/catalog` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/routes` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/diagnostics/pending-tallies` | covered | `--api --data` | `cli-api-shell.tryscript.md` |
| `/api/capabilities` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/index/progress` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/index/meta` | covered | `--api` | `cli-api-shell.tryscript.md` |
| `/api/git/repo` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/refs` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/summary` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/log` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/git/commit` | covered | `--api` | `cli-api-git.tryscript.md` |
| `/api/kpress/render` | covered | `--api`, `--api --data` | `cli-api-shell.tryscript.md` |
| `/api/kpress/export` | covered | `--api --data` | `cli-api-shell.tryscript.md` |
| `/api/plugin/agent-log/charts` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/binary/chunk` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/diff/document` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/diff/children` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/diff/comparison` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/plugin/structured/parsed` | covered | `--api` | `cli-api-plugins.tryscript.md` |
| `/api/events` | exempt | — | streaming; the response never terminates, so there is no envelope to pin |
| `/api/stream` | exempt | — | streaming; the response never terminates, so there is no envelope to pin |

`/api/kpress/export` is the one surface whose golden writes a file, and the rule it
settles is worth stating: a golden may write, into the tryscript sandbox, which is
created per run and discarded after it.
That is safe here because the export report’s paths normalize to `<ROOT>` and its
content hash is identical across runs and across sandbox paths, so the write is
deterministic evidence rather than a source of churn.
The test runs last in its file so no earlier test observes the written file.

The two exempt rows are the honest boundary.
A server-sent-event response has no terminating envelope, so `--api` bounds the request
and fails rather than hanging — which is behavior worth having, but not a model a
transcript can assert.
Their content is covered by `tests/dom/` and the event tests instead.

## Adding something

- **A kind**: add a `[[kind]]` block with a match predicate, and at least one
  `[[view]]`. Nothing else in core changes.
- **A view on an existing kind**: add a `[[view]]` block and `mb.registerView`; give it
  a disposal path.
- **A container**: add `container = { children = "<data_hook route>" }` to the kind and
  serve child rows from that hook.
  The tree, keyboard, ARIA, and URL behavior follow.
- **A data format**: it needs a schema, a conformance corpus both implementations run,
  and a normative doc — the bar the two formats above meet.
- **A route**: only when a genuinely new address space appears.
  A new kind of thing *within* an existing space extends that space’s path instead.

`tests/test_views_models_routes.py` checks the tables above against the manifests and
the route table, so this document fails the build rather than drifting.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
