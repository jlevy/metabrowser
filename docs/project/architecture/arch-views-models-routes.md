# Views, Models, and Routes

**Status:** Implemented, except two parts of the URL grammar marked planned below: the
`/compare/` routes and the reserved `_mb_` query keys.

The map of what Metabrowser shows, what it shows it from, and how each thing is
addressed: kinds, views, data formats, the browser URL grammar, and an index of routes.
Each route’s contract lives in the layer document the index names.
The tables that bind every route and user-visible behavior to `metab` evidence are in
the [Parity Registry](arch-parity-registry.md), and
[Architecture](../../architecture.md) maps the layers behind them.

## The Four Layers

A selection travels the same four layers whatever it is:

```text
address  ──►  resource kind  ──►  contract/model  ──►  view
what is      what the thing      the validated        how it
selected     can do              data                 is drawn
```

- **Address:** a route names the address space, and the path names the resource in it.
  The shell owns the core routes; a plugin adds data routes as `[[data_hook]]` entries
  under `/api/plugin/<plugin>/`.
- **Resource kind:** the classification a plugin claims.
  Filesystem `[[kind]]` blocks match a `FileContext`, content predicates included.
  Git blobs match by extension, basename, sniffed adapter, and bounded JSON, YAML, or
  frontmatter mappings parsed from the blob; `path_glob` is filesystem-only.
  A route-backed kind has no file matcher: the shell selects it for its route.
- **Contract/model:** the validated data a view receives.
  Simple kinds take the `/api/file` envelope; richer kinds have a documented format with
  a schema and a conformance corpus.
- **View:** a registered renderer (`[[view]]` plus `mb.registerView`), shown as a tab.
  A kind’s `default = true` view is what a selection opens.

A view never learns which source produced its model, and a model never learns which
route reached it, so one diff renderer serves a patch file, a commit, and a pull
request. Filesystem-backed models reach these layers through the
[Inventory Provider Contract](arch-inventory-provider.md), which keeps routes, wire
serializers, and views independent of the inventory engine.
A served Git revision reaches them through the source session
([Source Sessions and Pins](arch-source-sessions-and-pins.md)).

## Kinds and Their Views

The built-in kinds, as the manifests in `src/metabrowser/builtin_plugins/` and the
route-backed selections of `cli/show_cli.py` register them.
`tests/test_views_models_routes.py` checks this table against both.

| Kind | Matches | Views (default first) and keys | Model |
| --- | --- | --- | --- |
| `folder` | Directories | Agents `A`, the default, and Sessions `S` on a folder that is or holds an agent home; Overview `O` and Treemap `M` on every folder | Folder envelope and [File Rollup Format](file-rollup-format/file-rollup-format.md); Agents and Sessions read the `agents` catalog routes |
| `markdown` | `.md` | Document `V`, Source `S` | File envelope; KPress render |
| `mermaid` | `.mmd`, `.mermaid` | Diagram `V`, Source `S` | The file’s text as one `mermaid` fence through `/api/kpress/render`, drawn as a document’s diagrams are |
| `html` | `.html`, `.htm` | Preview `V`, Source `S` | File envelope; sandboxed raw document |
| `text` | Text files | Source | File envelope |
| `structured` | `.json`, `.yaml`, `.yml` | Tree `V`, Table `A` on a file that starts as a list of records (`structured/offer.py`), Source `S` | File envelope and the `structured/parsed` hook; Table reads a top-level list of mappings as one table through the `table/*` hooks ([Table Sources](arch-plugin-system.md#table-sources)) |
| `delimited` | `.csv`, `.tsv` | Table `V`, Source `S` | File envelope; one table through the `table/*` hooks, which the table plugin’s view draws ([Table Sources](arch-plugin-system.md#table-sources)) |
| `diff` | `.patch`, `.diff` | Diff | [File Diff Format](file-diff-format/file-diff-format.md) |
| `sqlite` | Any file that would otherwise be binary and starts with SQLite’s magic number, whatever its name (`magic`); `.sqlite`, `.sqlite3`, `.db`, `.db3`, and `.s3db` give the tree its chevron | Table `V`, Schema `S`, Info `I` | A container: the `sqlite/children` hook lists its tables, each at `<database>/<segment>`. Table is the overview at the database’s address, from `table/tables`, and the table plugin’s view at a table’s, through the `table/*` hooks ([Table Sources](arch-plugin-system.md#table-sources)); Schema reads `sqlite/schema` and Info `sqlite/info`, each read in a reader process |
| `sqlite-store` | An `fsqlite.json` whose `format` is `fsqlite`: an [fsqlite](https://github.com/jlevy/fsqlite) store’s marker, whose folder the tree badges (`folder_marker`) | Table `V`, Schema `S`, Info `I` | A container whose tables are the tables of the snapshot its `current` pointer names, each at `<marker>/<segment>` as a database’s are, listed by the `fsqlite/children` hook and read through the `table/*` hooks by the SQLite source over that snapshot (`builtin_plugins/fsqlite/source.py`). Table and Schema are the `sqlite` kind’s, Schema reading `fsqlite/schema`; Info reads `fsqlite/info`: the store’s marker, its version, its pending transaction envelopes, and that snapshot as the `sqlite/info` hook models a database. Every read is a guest’s (`builtin_plugins/fsqlite/store.py`) |
| `agent-log` | `.jsonl` sniffed as an agent log | Session `E`, Log `V`, Charts `C`, Raw JSON `S` | File envelope and the `agents/charts` hook; Session reads `agents/session` and `agents/records` |
| `agent-thread` | A compressed Codex rollout, `sessions/**/rollout-*.jsonl.zst`, claimed by its path | Session `E`, Log `V` | `agents/session` and `agents/records`, by the file’s path; the thread’s history store stands in for the unreadable rollout |
| `unknown-jsonl` | Other `.jsonl` | Log `V`, Raw JSON `S` | File envelope |
| `event-log` | A `.jsonl` file named `events-*.jsonl`, in a served folder (`path_glob`; a Git blob of that name is generic JSONL) | Timeline `V`, Latency `L`, By kind `B`, Errors `E`, Raw JSON `S` | File envelope and the `event-log/timeline`, `event-log/slowest`, `event-log/kinds`, and `event-log/errors` hooks over one segment of [the event log](../../realtime-debugging.md#event-log) |
| `image` | Browser image extensions | Image | File envelope; raw asset |
| `pdf` | A file that starts with `%PDF-` and would otherwise be binary (`magic`), whatever its name, and any `.pdf` | PDF | File envelope; the raw asset in the browser’s own viewer, with Open (in the macOS app), Download, and Open in new tab, and the first page behind it while it loads; a diff’s binary `.pdf` change, and a Markdown document’s embed of a `.pdf`, show the first-page card instead of a viewer, the document’s with a link to the PDF’s view. The first page is a PNG the server draws: `/api/plugin/pdf/preview` (by `path`, or a blob by `oid`) and `/api/plugin/pdf/preview-image` ([PDF plan](../specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md)) |
| `sqlite` | A file that would be `binary` and starts with `SQLite format 3\0` (a `magic` rule), whatever its name | Info | The `sqlite/info` hook: the database as a reader process read it ([Reading SQLite Databases](arch-plugin-system.md#reading-sqlite-databases)) |
| `binary` | Non-text files | Bytes | The `binary/chunk` hook’s bounded byte windows |
| `comparison` | No file; the Commits tab selects it for `/commit/<rev>[/<inner>]` | The `diff` kind’s views | `diff/comparison` document in File Diff Format |
| `pull-request` | No file; the shell selects it for `/pull/<n>[/files[/<path>] or /checks]` | Pull request, which draws its own Conversation `C`, Changes `G`, and Checks `E` tabs | `github/pull` envelope and the hooks it names; beside its record, the operational status (`PullStatus`), its head’s checks (`PullChecks`), both in `pull_status.py`, and the verdict on them (`Readiness`, `pull_readiness.py`) ([Operational Status](arch-github-pull-requests.md#operational-status)) |
| `pull-stack` | No file; the shell selects it for `/stack/<n>[/guided, /docs, or /changes[/<path>]]` | Stack, which draws its own Diff summary in its header and its own Guided Review, Docs, and Changes tabs | `github/stack` envelope, the `github/stack-comparison` document it names, the `github/guided-review` answer by `stack`, and the `github/pull-statuses` answer for its open members, whose readiness ends their rows |
| `pull-request-list` | No file; the Pulls tab mounts it, and the pane at `/pulls` | Pull requests | `github/pulls` envelope, and the `github/pull-statuses` answer for the open rows it draws, each row’s readiness; a stack menu’s members on a pull request’s page read it too |

A view’s key is its manifest `[[view]] key`, written here uppercase as the keyboard
shows it and served lowercase as the envelope’s `views[].key`. A single-view kind
declares none, and a list left with one view serves none (`keymap.live_view_keys`).
`tests/test_keymap.py` fails when two views of a kind share a key or a view takes a key
the shell reserves for that kind (`RESERVED_SHELL_KEYS` in `src/metabrowser/keymap.py`),
and `cli-show.tryscript.md` prints each kind’s views with their keys.
A rendered view takes `V` and a source view `S`, by the rules in
[Keyboard Shortcuts](../../design-system.md#keyboard-shortcuts).

`devtools/check_parity.py` fails the build when a kind a built-in manifest declares or
consumes has no exact `kind: <id>` line in the output of a successful `--show` command
in a golden transcript.

The `table` plugin has no kind: it owns the `table/*` hooks, which serve every kind a
plugin declares a `[[table_source]]` for, and the table view, which a source plugin
mounts for its kind’s Table view through `mb.plugins.load("table")`
([Table Sources](arch-plugin-system.md#table-sources)).

Four kinds are also **containers**, folder-like entries whose children are addressable
([Plugin System](arch-plugin-system.md)): `folder`, whose children are files and
folders, `diff`, whose children are the files a patch changes, `sqlite`, whose children
are a database’s tables, views, and virtual tables, and `sqlite-store`, whose children
are the tables of the snapshot its `current` names (the `fsqlite/children` hook, through
`builtin_plugins/fsqlite/source.py`). A kind declares one with
`container = { children = "<data_hook route>" }`.

### Shared Source Rendering

`text`, `structured`, `markdown`, and `html` expose raw source from the file envelope.
The text and structured views use the SDK’s shared Source renderer; Markdown keeps its
own frontmatter split but follows the same language and size decisions.
A source view never embeds another kind’s renderer, because a nondefault plugin mounts
on demand and may not be loaded.

The server owns the logical-extension and basename grammar maps and the syntax byte
bound, and injects them with the file envelope settings.
A renderer emits exact escaped text and a language class; the shell enhances the mounted
subtree after the renderer settles and after first paint.
Diff views need tokens in their line model rather than markup, so they call the SDK’s
bounded token service with the same registry, grammars, and palette.
Intraline ranges are browser-local enrichment over exact line text, and neither
enrichment extends File Diff Format v1. `test_plugin_sdk_syntax_token_contracts` and
`test_syntax_language_extensions_are_always_browser_text` check the registry against the
vendored grammars and the text routing.

## Documented Data Formats

A complete format has a schema, a conformance corpus, and implementations bound by it.
Both are tool-neutral: nothing in a document references Metabrowser.

| Format | Describes | Authority | Implementations |
| --- | --- | --- | --- |
| [File Diff Format v1](file-diff-format/file-diff-format.md) | A change set between two snapshots | `data/file-diff-format/file-diff.schema.json` | `metabrowser.diff.format` (Pydantic), `builtin_plugins/diff/diff-model.js` |
| [File Rollup Format](file-rollup-format/file-rollup-format.md) | File classification and directory totals | `data/file-rollup-format/` | `inventory_rollup.py`, the browser rollup projection |

The repository cache’s record contracts are an internal format: their installed
inventory is maintained by `devtools/check_artifact_contracts.py`, described in
[Repository Cache](arch-repository-cache.md), and this map registers no kind or view for
them. The list of [recent targets](arch-recent-targets.md), `recent-targets.yml` in the
configuration directory, is an internal format as well, read only through `metab`.
Everything else travels as an envelope on `/api/*`, versioned with the shell and the
built-in plugins as one artifact: an internal contract, not a standard.
The table routes’ envelopes are one such contract, defined in one module,
`metabrowser.table_source`, for every source.
[Where diff documents come from](arch-diff-pipeline.md#where-documents-come-from) maps
the sources that produce diff documents.

## Browser URL Grammar

A browser URL answers four questions, and each component answers one:

| Component | Question | Owned by |
| --- | --- | --- |
| Route | Which kind of thing is selected | Metabrowser |
| Path | Which one, within that kind | That kind’s address space |
| Query | How it is presented | The link author |
| Fragment | Where inside the rendered document | The document |

There is one route per address space, because a path means something only once you know
which space it belongs to.
`tests/test_view_routes.py` checks the grammar, and the contracts are in the documents
the last column names.

| Route | Selects | Path is | Contract |
| --- | --- | --- | --- |
| `/view/<path>` | Content in the served folder or pinned revision; `/view/` is the root | A served-root-relative path, or a `GitPath` wire on a pin | [Server and Content](arch-server-and-content.md) |
| `/view/<container>/<inner>` | One entry inside a container file | A container’s address, then a path within it | [Plugin System](arch-plugin-system.md) |
| `/commit/<rev>` | A commit’s change set against its first parent | A full commit ID; the page refuses anything else as `revision_not_full` | [Git](arch-git.md) |
| `/commit/<rev>/<inner>` | One file’s diff in that change set | A commit ID, then a path; the Commits tab restores the commit, not yet the file | [Git](arch-git.md) |
| `/pull/<n>`, `/pull/<n>/conversation`, `/pull/<n>/docs`, `/pull/<n>/files`, `/pull/<n>/guided`, `/pull/<n>/checks` | A pull request’s front page (Guided Review when its description carries a guide, Conversation otherwise), or its Conversation, Docs, Changes, Guided Review, or Checks tab | A pull-request number, then a tab | [GitHub Pull Requests](arch-github-pull-requests.md) |
| `/pull/<n>/files/<path>` | Changes, at one changed file | A number, then a path in its comparison, never looked up on disk | [GitHub Pull Requests](arch-github-pull-requests.md) |
| `/pulls` | A repository’s pull requests, with none selected | None; `?state=` names the filter | [GitHub Pull Requests](arch-github-pull-requests.md) |
| `/stack/<n>`, `/stack/<n>/guided`, `/stack/<n>/docs`, `/stack/<n>/changes` | A native stack’s front page (Guided Review when a member’s description carries the stack’s guide, Changes otherwise), or its Guided Review, Docs, or Changes tab | GitHub’s stack number, then a tab | [GitHub Pull Requests](arch-github-pull-requests.md#the-stack-page) |
| `/stack/<n>/changes/<path>` | Changes, at one file of the stack’s comparison | A number, then a path in that comparison, never looked up on disk | [GitHub Pull Requests](arch-github-pull-requests.md#the-stack-page) |
| `/compare/<base>..<head>[/<inner>]` | An explicit comparison, `...` for the merge base | Two revisions, then a path | Planned, not built |

A revision is not a path in the served tree, so it gets its own route rather than a
sigil inside `/view/`, where it would collide with a real file or need an escape every
path handler would have to know.
After the route, the shape is always `<container address>/<inner path>`, the container
contract written as a URL: `/view/changes.patch/src/app.py`, `/commit/<rev>/src/app.py`,
and `/pull/7/files/src/app.py` are one grammar over three address spaces.
A branch is not an address space: opening a repository resolves it to a full commit and
pins a `GitRevisionSubject`, and `/view/<path>` then addresses content by `GitPath`.

Route invariants:

- A route without a path selects its space’s root: `/view/` is the served root, and the
  bare `/` redirects there with a 307 so the root has one URL.
- A served-tree path has one canonical, lossless spelling, written by `view_routes.py`
  and `static/navigation.js`; the server restores the platform path before its
  containment and symlink checks.
- Every selection the shell can make has a URL, and reloading it restores the selection.
- A fragment is a location inside the document, never a file.
  A fragment spelled as a line anchor (`#L10`) is always one, as on github.com, and
  opens the Source view; so does GitHub’s `plain=1` query key.
- The query is carried verbatim, and an unknown route is a not-found response, never a
  redirect to `/view/`.

The query is the one component with two authorities in it, so it needs a reserved
namespace. **Planned, not built:** Metabrowser will reserve query keys beginning with
`_mb_` for presentation the sender decides, such as `_mb_view=source`, and pass every
other key to the document untouched.
The prefix pairs the usual mark of a reserved field with the owner’s name, because a
bare `_` already marks non-contract surfaces here (`/_debug/tasks`). The reservation
keeps one invariant: removing every `_mb_` key from a URL yields that content’s
canonical URL. Viewer-owned settings such as theme stay out of links; reserved keys are
sorted and never dropped for matching a default; and an unrecognized `_mb_` key is a
visible diagnostic. The first entries are mapped in the
[Markdown navigation extensions plan](../specs/active/plan-2026-08-13-markdown-navigation-extensions.md).

## Data Routes

`tests/test_views_models_routes.py` fails when a route that `devtools/check_parity.py`
counts is missing here; the asset routes are not counted.

| Route | Serves | Contract |
| --- | --- | --- |
| `/api/file` | The file or folder envelope: kind, views, and a bounded content window | [Server and Content](arch-server-and-content.md) |
| `/api/kpress/render`, `/api/kpress/export` | KPress rendering, reduced to inert HTML in the Markdown child under a deadline when active content is off, and export | [Server and Content](arch-server-and-content.md) |
| `/raw`, `/raw/<path>` | Bounded raw bytes with sandbox headers, and the document the HTML Preview frames | [Server and Content](arch-server-and-content.md) |
| `/static/<path>`, `/plugin-static/<plugin>/<path>`, `/kpress-static/<path>` | Shell, plugin, and KPress assets at addresses stamped by content (`asset_stamps.py`) | [Server and Content](arch-server-and-content.md) |
| `/api/routes` | Every route this build serves | [Server and Content](arch-server-and-content.md) |
| `/_debug/tasks`, `/_debug/inventory` | Task and inventory diagnostics, served only with `METABROWSER_DEBUG=1` | [Server and Content](arch-server-and-content.md) |
| `/api/tree`, `/api/rollup`, `/api/catalog`, `/api/recent` | Navigation pages, folder rollups, the file universe for Quick Search, and newest-first leaves | [Inventory Provider](arch-inventory-provider.md) |
| `/api/index/progress`, `/api/index/meta`, `/api/capabilities` | Index progress and metadata, and what the active source supports | [Inventory Provider](arch-inventory-provider.md) |
| `/api/tree`, `/api/index/progress`, `/api/capabilities` on a pinned revision | A node’s `mtime` and the `ages` state of getting it, and `file_ages` in what the source supports | [File Ages](arch-git.md#file-ages) |
| `/api/tree` with `recency` or `group_by=age`, `/api/recent`, and `/api/file` on a pinned revision | Modified within, By age with its Undated group, the newest files of a window, and a file’s `mtime` from the answer that is there, from the same times | [File Ages](arch-git.md#file-ages) |
| `/api/events` | The server-sent inventory snapshot and changes | [Live Delivery](arch-live-delivery.md) |
| `/api/events/watch` | A file watch registered on one `/api/events` connection, whose changes arrive there as `file.changed` | [Live Delivery](arch-live-delivery.md#file-watches) |
| `/api/stream`, `/api/activity` | The live tail of a JSONL file, and the files being written now | [Live Delivery](arch-live-delivery.md) |
| `/api/diagnostics/pending-tallies` | `POST`: a client’s pending-tally warning, matched with server state | [Live Delivery](arch-live-delivery.md) |
| `/api/event-log` | Where the structured event log is, its segments, and its records filtered by kind, outcome, cause, span, client (a request’s, or a page’s and every request it sent), and duration, with the spans this process has open (`event_log_route.py`) | [Real-Time Debugging](../../realtime-debugging.md#event-log) |
| `/api/event-log/failures` | The failures in the event log since a moment, an hour ago by default, grouped by cause, with the addresses that failed, the latest message, links to their records, and the latest failed connectivity probe; a page’s own reports of failure listed apart, under `page_reports` (`event_log_route.py`) | [Real-Time Debugging](../../realtime-debugging.md#github-failures) |
| `/api/event-log/client` | `POST`: what a page saw, its slow and pending requests, frozen frames, and waits still running at the late threshold, checked, bounded, redacted, and written as `browser` records under the page’s client ID (`event_log_reports.py`, sent by `static/event-reports.js`) | [Real-Time Debugging](../../realtime-debugging.md#what-the-page-reports) |
| `/api/git/repo`, `/api/git/refs`, `/api/git/summary`, `/api/git/log`, `/api/git/commit/<rev>`, `/api/git/commit-markdown/<rev>`, `/api/git/commit-size/<rev>` | Read-only history for the Commits tab, of the revision the Files tab shows: a folder’s working tree’s own, and a checkout revision’s or a mirror pin’s commit’s; a commit’s size as Git pushes it and as a patch (`git/change_size.py`) | [Git](arch-git.md), [Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout) |
| `/api/source/status`, `/api/source/refs`, `/api/source/pin` | What the server serves; the served root’s branches and tags, a mirror’s or a repository folder’s, with a checkout’s remote-tracking branches, each with its commit’s full ID and committer date, and a checkout’s working tree by its folder and where its `HEAD` is, which `kind=working_tree` answers alone with no Git process, and the pull requests each branch is the head of, as its provider has cached them, which the filter finds a branch by too; for a repository folder that keeps a store of its origin, that store’s state (`origin`) and the origin’s branches and tags from it; and switching its view: a mirror’s pin, or a checkout between a revision and its working tree. `metab PATH --ref NAME` starts a checkout on a revision, so every route that answers a pin answers a checkout’s revision from a terminal | [Source Sessions and Pins](arch-source-sessions-and-pins.md), [Open Modes](arch-open-modes.md) |
| `/api/identity` | What the served subject is called, for a window’s title, which of three kinds of root it is (`folder`, `git`, or `mirror`) and the sentence for the mark that names it, and the GitHub repository it belongs to (`root_identity.py`) | [Source Sessions and Pins](arch-source-sessions-and-pins.md) |
| `/api/counterpart` | The github.com page that shows what a page shows, for its View on GitHub control, or why there is none (`counterpart.py`) | [Design System: View on GitHub](../../design-system.md#view-on-github) |
| `/api/source/refresh` | `POST`: start or join a background refresh of the served mirror, or of the store a repository folder keeps of its origin; with `{"for": "commit"}`, the fetch a commit the mirror lacks waits for; with `{"for": "page"}`, a visible page’s own ask, which probes the served branch at its origin and fetches when it moved | [Refresh Cadence](arch-mirror-acquisition-and-refresh.md#refresh-cadence) |
| `/api/source/link` | `POST`: open a link into the served mirror’s repository: start a refresh, switch the pin to the revision a branch, folder, or file link names, and answer the page to go to, a pull request’s or a commit’s with no switch | [GitHub Links](arch-macos-app.md#github-links), [Source Sessions and Pins](arch-source-sessions-and-pins.md) |
| `/api/cache/layout`, `/api/cache/sources`, `/api/cache/source/<slug>`, `/api/cache/stores` | Read-only logical state of the repository cache (`cache/wire.py`) | [Repository Cache](arch-repository-cache.md) |
| `/api/plugin/<plugin>/<route>` | A plugin’s `[[data_hook]]` | [Plugin System](arch-plugin-system.md) |

Plugin hooks currently registered: `diff/document`, `diff/children`, and
`diff/comparison` ([Diff Pipeline](arch-diff-pipeline.md)); `fsqlite/info`,
`fsqlite/schema`, and `fsqlite/children` (an fsqlite store, above); `binary/chunk`,
`structured/parsed`, and `agents/charts` ([Plugin System](arch-plugin-system.md));
`event-log/timeline`, `event-log/slowest`, `event-log/kinds`, and `event-log/errors`
([Real-Time Debugging](../../realtime-debugging.md#browsing-the-log)); `agents/catalog`,
`agents/sessions`, `agents/session`, `agents/records`, and `agents/live`, the catalog of
Claude Code and Codex sessions under a served folder ([Agent Catalog](#agent-catalog));
`table/tables`, `table/schema`, `table/rows`, `table/record`, and `table/card`
([Table Sources](arch-plugin-system.md#table-sources)); `sqlite/info`, `sqlite/schema`,
and `sqlite/children`, a SQLite database’s Info and Schema views and its tables as
container children
([Navigation Containers](arch-plugin-system.md#navigation-containers)); `pdf/preview`
and `pdf/preview-image`, a PDF’s first page as a PNG the server draws
([PDF plan](../specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md)); and
`github/pull`, `github/pull-refresh`, `github/pull-cores-prepare`,
`github/pull-comparison`, `github/pull-image`, `github/pull-rendered-diff` (a changed
file’s rendered projection; for Markdown, in Full, in Concise, or a range of its blocks,
by [Markdown Views](arch-diff-pipeline.md#markdown-views)), `github/pull-size`,
`github/pull-timeline`, `github/pull-markdown`, `github/guided-review`, `github/pulls`,
`github/pulls-refresh`, `github/pulls-prefetch`, `github/pull-files`,
`github/pull-files-refresh`, `github/pull-files-summary`, `github/pull-statuses`,
`github/stacks`, `github/stacks-refresh`, `github/stack-change`, `github/stack`,
`github/stack-comparison`, `github/labels`, `github/labels-refresh`,
`github/cache-clear`, and `github/status`
([GitHub Pull Requests](arch-github-pull-requests.md)).

## Agent Catalog

The `agents` plugin keeps a catalog of the Claude Code and Codex sessions under a served
folder and answers five data hooks from it.
The
[operational views plan](../specs/active/plan-2026-11-19-agent-operations-views.md#engines-and-the-catalog)
gives the design. `builtin_plugins/agents/homes.py` decides which folders hold a home
(`homes_in`, and `holds_homes` for a view’s `offer`), `catalog.py` keeps the sessions
current on a worker thread, `store.py` caches each summary, and `routes.py` serves them.

| Route | Parameters | Returns |
| --- | --- | --- |
| `catalog` | `folder` | Homes, totals, size-histogram buckets, sessions per day, progress, freshness, cache state, drift, and engines |
| `sessions` | `folder`; filters `agent`, `origin`, `status`, `project`, `model`, `since`, `until`; `sort`, `order`, `limit`, `offset` | Matching rows, `total`, `next_offset`, and facets over the whole folder |
| `session` | `agent` and `id`, or `path`, the session’s source file | One row, its parent, its children, and its drift |
| `records` | the session as above; `kind`, `tool`, `locator`, `limit`, `cursor` | One page of the session’s normalized events, with `next_cursor`, which is null at the end and where the scan bound stopped (`truncated`) |
| `live` | `folder` | Sessions a pid file, an active turn, or a recent update vouches for |

Paths in `folder` and `path` are served-root-relative and resolve through `plugin_api`;
every path in a response is relative to the served root, and a project shows the user’s
home directory as `~`. A refusal is `{"error", "code", "param"}` with status 400 or 404,
or 503 `catalog_incomplete` (with `progress`) for a session that the first pass of a
home has not listed yet, which a page asks for again.

A request answers from what the worker has summarized so far and reports `progress` and
`freshness`; it starts a pass when the last is old, and never waits for a full one.
`sync=1` waits until the catalog is fully summarized, which is how `metab --api`, tests,
and goldens get a complete answer.
One such request waits at a time, for one deadline shared by its homes
(`SYNC_TIMEOUT_SECONDS`); another answers at once with the progress so far.
`now` (Unix seconds) replaces the clock of the response and its liveness checks, never
the catalog’s own pass times.
Each summary is cached in `plugin_cache_directory("agents")`, keyed by the session’s
source files, sizes, modification times, and measure-family versions (`session_key`), so
a change re-reads only that session.
When no private cache directory can be made, `cache.state` is `unavailable` and the
routes answer from memory.
The limits and the measurements that set them are beside their constants, in
`catalog.py`, `routes.py`, `store.py`, `readers.py`, and `codex.py`.

### Agent Views

The plugin’s surfaces are views of kinds that already exist, so each is reached by
`metab --show` and reads only the routes above (no plugin can register an address space
of its own).

| View | Kind | Offered | Reads |
| --- | --- | --- | --- |
| Agents (`agents`), the default | `folder` | Where `holds_homes` accepts the folder: a Claude Code or Codex home, or a folder holding `.claude` or `.codex` | `catalog`, `sessions` for the recent rows, `live` |
| Sessions (`agent-sessions`) | `folder` | The same | `sessions`, one page at a time, with its filters, sort, and page |
| Session (`session`), the default | `agent-log`, `agent-thread` | Every file of the kind | `session` and `records` by the file’s `path`; a file in no agent home falls back to the Log |
| Log (`log`) | `agent-thread` | Every file of the kind | `records` by `path` |

The views’ code and stylesheet (`agents-views.css`) are on demand: `index.js` registers
a stub for each and imports the module the first time its view is shown, because the
plugin’s own assets load for every folder page.
What the browser owns is in `session-list-state.js` (filters, sort, and paging),
`poller.js` (when a page asks again), and `home-model.js` (what the home derives), each
pinned browserlessly by `tests/dom/agents-views-session.js`.

## Adding Something

- **A filesystem-backed kind:** add a `[[kind]]` block with a match predicate and at
  least one `[[view]]`, then a representative `--show` case in a golden transcript.
- **A route-backed kind:** declare a `[[view]]` for a kind no `[[kind]]` matches and
  have the shell select it for its route, as the GitHub plugin’s `pull-request` kind is
  for `/pull/<n>`; add the route, its `--api` golden, and its parity rows in the same
  change. Do not invent a file matcher.
- **A view on an existing kind:** add a `[[view]]` block and `mb.registerView`, give it
  a disposal path, and register each new observable behavior in the
  [Parity Registry](arch-parity-registry.md).
- **A container:** add `container = { children = "<data_hook route>" }` to the kind and
  serve child rows from that hook; the tree, keyboard, ARIA, and URL behavior follow.
- **A data format:** a schema, a conformance corpus both implementations run, and a
  normative document, as the two formats above have.
- **A route:** only for a new address space.
  A new kind of thing within an existing space extends that space’s path instead.

Registering a kind, view, route, or format updates this map in the same change.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
