# Plugin System

**Status:** Built: manifest discovery from three sources, declared dependencies between
plugins, declarative kind classification, the SDK version gate, Python data hooks, JSONL
adapters, table sources served by the `table` plugin’s routes, and two container kinds,
directories and patch files.
Planned: editing through plugins
([trusted-local editing plan](../specs/active/plan-2026-07-16-trusted-local-file-editing.md)).
Planned: archive containers
([archive plan](../specs/active/plan-2026-11-24-archive-contents-and-browsing.md)).
Proposed, with no plan yet: re-rooting the tree at a container.

Metabrowser shows any file type through plugins.
Every built-in view is a plugin in `src/metabrowser/builtin_plugins/`, loaded through
the same manifest, browser SDK, and data-hook contract an installed plugin uses, so core
holds no renderer for any format.
[Plugin Authoring](../../plugins.md) is the author’s reference for that contract.
This document is how the host implements it, and the path for adding a file type.

## Modules

| Module | Owns |
| --- | --- |
| `plugin_loader/manifest.py` | The manifest schema, its consistency checks, `PLUGIN_SDK_VERSION`, and the view merge |
| `plugin_loader/discovery.py` | The three discovery sources, plugin-name collisions, and refusing unmet requirements |
| `plugin_loader/classify.py` | Compiling `[[kind]]` rules into one classifier, and the bounded content predicates |
| `plugin_loader/static_assets.py` | The `/plugin-static/` and `/api/plugin/` routes and data-hook dispatch |
| `file_kinds.py` | `FileContext`, the built-in view registry, and the fallback detector chain |
| `file_extensions.py` | The syntax registry and the text, image, and live-tracked extension sets |
| `plugin_api.py` | The Python sidekick API that `metabrowser` re-exports |
| `table_source.py` | The table source protocol, its wire contract and bounds, and the registry the table routes resolve a path through |
| `cli/plugins.py` | `metab --plugins`, `--plugin`, and `--doctor` |
| `static/plugin-sdk.js`, `static/plugin-sdk-views.js` | The `window.metabrowser` browser SDK |

The browser half, including how the shell loads a plugin’s assets and mounts its views,
is in [Browser Shell](arch-browser-shell.md).

## Discovery

The server discovers plugins once, when `server.py` is imported, so a changed manifest
needs a restart. Every CLI mode resolves operator directories through
`cli/plugin_paths.py`: the diagnostic modes pass them to `discover_plugins`, and a mode
that imports the server publishes them in `METABROWSER_PLUGINS_DIRS` first, so every
mode sees one plugin set.
[Plugin Authoring](../../plugins.md#trust-model-and-discovery) owns the source order and
the trust boundary it enforces.

- **Collisions:** plugins are kept by name, and a later source replaces an earlier one,
  with a log line, in the earlier one’s place.
  That order is the discovery index that breaks kind priority ties.
- **Failures:** a directory with `manifest.toml` but no `index.js`, or a manifest that
  fails validation, becomes an error string, and that plugin is skipped.
  The server still starts; the CLI modes print the errors and exit nonzero.
- **Operator directories are JavaScript-only:** `build_plugin_routes` mounts no data
  hook for a plugin discovered from `--plugins-dir`, and logs that it ignored them.
  Python runs only from a built-in or an installed distribution, which already belongs
  to the environment.
- **Register modules:** a manifest’s optional `[plugin] register` names a Python module
  that discovery imports once, as it loads a built-in or entry-point plugin, so the
  plugin can register extensions such as log adapters.
  An import failure becomes an error string like any other load error and the plugin is
  skipped. For an operator-directory plugin the field is ignored with a logged warning,
  as data hooks are, and `metab --doctor` reports it.
  Discovery runs at server start and in the plugin-inspection modes, not on `--version`
  or `--present --dry-run`, so those do not import a register module.

## Declared Dependencies

A manifest’s `[plugin] requires` names the plugins whose exports its browser code loads
with `metabrowser.plugins.load(name)`
([Plugin Authoring](../../plugins.md#declared-dependencies)). `resolve_requirements` in
`discovery.py` runs on the plugin in use for each name, once collisions are settled, so
it sees the plugin set the server serves:

- A plugin that requires itself fails its own manifest’s validation.
- A plugin on a longer cycle is refused, with the shortest cycle back to it, since two
  modules that each wait for the other’s exports never finish.
- A plugin that requires one that was not discovered, or was refused, is refused in
  turn, so a refusal reaches everything that depends on it.
- A plugin that declares a `[[table_source]]` fails its own manifest’s validation unless
  it requires `table`, whose routes serve it, so a missing table plugin refuses every
  source plugin.
- A plugin that replaced another by name and is refused gives the name back:
  `discover_plugins` restores the plugin it replaced and resolves again, as if the
  replacement’s manifest had been invalid, so one operator’s typo cannot refuse the
  built-ins that require the plugin it shadows.

Each refusal is a discovery error, so the server logs it and the CLI modes print it and
exit nonzero. The kept plugins stay in discovery order, which breaks kind priority ties.
A provider is not loaded before its dependents: in the browser, `plugins.load` loads it
on demand and shares the one load that selecting its kind would start
([Plugin Assets](arch-browser-shell.md#plugin-assets)), because the built-in providers
are on-demand tiers whose consumers need them only for some pages, such as a folder with
a README or a pull request with a diagram.
`metab --doctor` reports the graph it kept, and `--plugins` and `--plugin NAME` show
each plugin’s `requires`. `tests/test_plugin_requirements.py` checks that each built-in
plugin loads exactly the providers it declares.

## Manifests

`load_manifest` parses `manifest.toml` with `tomllib` into Pydantic models that forbid
unknown keys, then `PluginManifest.validate_consistency` collects every problem at once:
the SDK gate below, an empty or contradictory match predicate, a duplicate view id or
second default view in a kind, a data-hook route that repeats or contains `/`, a
malformed `module:callable`, a container naming a route the plugin does not declare, and
an extra asset that is not a plain filename.
`keymap.view_key_error` refuses a view key that is not one letter, or that the shell
reserves in every kind.

A kind’s tabs are `merge_views` of the built-in `VIEW_REGISTRY` in `file_kinds.py` and
every plugin’s `[[view]]` entries in discovery order.
A view whose id matches an earlier one replaces it in place.
`keymap.check_view_keys` then drops a contested or reserved key from the later view, and
`metab --doctor` reports the plugins on both sides, since it merges through the same
function the server serves.

## The SDK Version Gate

`PLUGIN_SDK_VERSION` in `plugin_loader/manifest.py` is the browser contract this host
provides. A manifest’s `sdk_version` must equal it; an omitted value resolves to
`_IMPLICIT_PLUGIN_SDK_VERSION`, the original SDK, never to the host’s current one.
A mismatch is a validation problem, so the plugin is refused at load with a message
naming the required version, and `metab --doctor` reports it first.
There is no negotiation and no shim.
An additive SDK method does not change the version; a break bumps it and every built-in
manifest in one commit.
[Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code)
gives the reasons.

## Classification

`_api_file_impl` in `server.py`, behind the `/api/file` route `api_file`, decides a
file’s kind in this order:

1. A directory is `folder`. A folder view that declares `offer` is served only where its
   predicate accepts the folder, off the event loop, and an offered default becomes the
   folder’s only default (`_offered_folder_views` in `server.py`).
2. A path that does not exist is offered to the containers below.
3. A `.jsonl` file is parsed, and its sniffed adapter joins the classifier’s input.
4. An extension in `BROWSER_IMAGE_EXTS` is `image`.
5. A file read as text, because its extension is in `BROWSER_TEXT_EXTS` or because
   `content_sniff` finds text, runs the plugin classifier, then the fallback chain
   `FILE_KIND_DETECTORS` in `file_kinds.py`, then defaults to `text`. A view of its kind
   that declares `offer` is served only where its predicate accepts the file’s leading
   bytes (`_offered_file_views` in `server.py`), as a pinned text blob’s view is; the
   other steps read no bytes for an offer, so their kinds’ offered views are never
   served.
6. Anything else is checked against every `magic` rule, whatever its name, from the
   sniff prefix step 5 already read, on the bytes on disk; the first match is its kind.
7. Anything left is asked of the `binary = true` rules, which match by path alone
   (`_binary_kind`), and is `binary` when none claims it.

Ordinary `[[kind]]` rules therefore see text and JSONL files only; a `magic` rule and a
`binary` rule see only files found to be binary.
`match.magic = {offset, hex}` names bytes at an offset within `MAGIC_MAX_END`
(`plugin_loader/manifest.py`, the sniff prefix), and `classify_magic` in
`plugin_loader/classify.py` checks it by priority, then discovery order.
A magic rule takes only `ext` or `exts` beside it, which decide the tree’s container
chevron and nothing else, so a `.db` file that is not SQLite stays binary and a database
named `History` is SQLite.
A compressed file is checked on its compressed bytes, so `x.sqlite.gz` stays binary.
Every classification site applies it: `api_file`, the container walk
(`_classify_content_kind`), the table routes’ kind on a served folder and on a pin, and
a Git blob (`plugin_magic_kind` in `git/content_routes.py`), which a stored blob’s own
bytes decide. A plugin claims any other binary format with a `binary` rule, or adds a
view to the `binary` kind.

`build_classifier` sorts every loaded rule by descending `priority`, then discovery
index, and returns the first match.
Fields within one rule combine with AND, and rules sharing an id are alternatives.
The content predicates read lazily through `FileContext` and are bounded:
`_JSON_CLASSIFICATION_MAX_BYTES` admits only a complete JSON document, and
`_YAML_PREFIX_BYTES` parses a prefix.
Every front-matter read, of a plain file, a compressed Markdown file, or a Git blob,
stops at `FRONTMATTER_MAX_BYTES`, and both YAML predicates parse through the bounded
loader in `frontmatter_yaml.py`. It refuses a document that nests past `YAML_MAX_DEPTH`
or is larger than its budget written out without its YAML aliases
(`FRONTMATTER_MAX_EXPANDED_SIZE` for front matter, `_YAML_PREFIX_MAX_EXPANDED_SIZE` for
the YAML prefix) before building it, and builds every collection and merge key itself,
leaving ruamel’s constructor only the scalars.
Compressed files classify by their logical name, so `notes.md.gz` is Markdown.

A Git blob has no filesystem path, so `classify_identity` applies the same rules without
`path_glob`, and content predicates match only when the caller parsed the blob’s bytes
(`git/content_routes.py`). A `folder_marker` rule also hands its basename to
`tree.set_folder_markers`, which badges the parent directory’s row.

A route-backed kind has no `[[kind]]` rule.
The GitHub plugin declares views for `pull-request` and `pull-request-list`, and the
shell selects those kinds for `/pull/<n>` and `/pulls`. The built-in kinds and their
views are mapped in
[Views, Models, and Routes](arch-views-models-routes.md#kinds-and-their-views), which
`tests/test_views_models_routes.py` checks against the manifests.

## Data Hooks and Plugin Files

`build_plugin_routes` mounts one route per `[[data_hook]]` at
`/api/plugin/<plugin>/<route>`, with the methods the manifest lists.
The sidekick callable is imported once at startup; a hook whose import fails is skipped
with a warning, and the rest of the plugin still loads.
The dispatcher awaits an `async def` handler and runs a synchronous one in Starlette’s
threadpool. An exception, or a response of status 500 or above, is logged and answered
with a `plugin_error` JSON body instead of a server error, so one broken hook degrades
its own view and nothing else.

`/plugin-static/<plugin>/<file>` serves the plugin’s directory through a traversal
guard. The shell addresses those files under a stamp of the whole directory, which
`asset_stamps.py` defines, so a browser keeps them until the directory changes.

## Table Sources

The built-in `table` plugin owns the routes every tabular source answers through, and
has no kind of its own.
A source plugin claims a kind, requires `table`, and names the Python adapter that
answers for that kind:

```toml
[plugin]
name = "delimited"
requires = ["table"]

[[kind]]
id = "delimited"
match = { exts = [".csv", ".tsv"] }

[[table_source]]
kind = "delimited"
adapter = "metabrowser.builtin_plugins.delimited.source:adapter"
```

`table_source.py` in core holds the protocol, so core imports no plugin, and
`plugin_api.py` re-exports what a source implements as SDK surface: the types, errors,
cell and token helpers, and bounds, but not the registry or the routes’ wire functions.

- **Registration.** A `[[table_source]]` names one of its own plugin’s kinds, once, and
  its plugin must require `table`; `validate_consistency` refuses anything else.
  `server.py` installs every declaration of a plugin allowed to run Python
  (`install_table_sources`), so an operator-directory plugin’s are ignored with a log
  line, as its data hooks are, and `metab --doctor` reports them and any adapter that
  does not import. A later declaration for a kind replaces an earlier one.
- **Dispatch.** Each route takes `?path=`. `open_table_source` resolves it through the
  content reader, classifies it as `/api/file` does (the full classifier on a served
  folder, the extension and basename rules on a Git pin), imports that kind’s adapter on
  first use, and hands it a `TableHandle`: the `ContentRef`, the file’s name, and its
  resolved real path on a served folder.
- **The adapter** is a callable from a handle to a `TableSource`, whose methods are
  synchronous and run on the route threadpool under one request’s `Budget`. A source
  reads through `TableHandle.read_window`, which runs the content read on the event loop
  and waits for it, and keeps any cache in its own module, keyed by its `generation()`.
- **The wire.** `tables_wire`, `schema_wire`, `page_wire`, `record_wire`, `card_wire`,
  and `error_wire` are every route’s answer, so two sources cannot drift apart.
  The query grammar (`parse_table_query`, checked against the schema by
  `check_table_query`), the cell envelopes, and the key, position, and cursor tokens are
  defined there as well, with the bounds every route applies beside the measurements
  that set them.

| Route | Serves |
| --- | --- |
| `/api/plugin/table/tables?path=` | The source’s tables, each with its group, whether its rows have a key, an estimate where the source has one, and its address |
| `/api/plugin/table/schema?path=` | Field descriptors, key fields, default columns, and references in both directions |
| `/api/plugin/table/rows?path=&…` | One page in the collection envelope, for `sort`, `order`, `q`, `f.<field>=<op>:<value>`, `ref=<table>:<key>` (split at its last colon), `cols` (one field per parameter, repeated), `after`, and `limit` |
| `/api/plugin/table/record?path=&key=` | One record, each value previewed past the record bound, and whether the generation the key was read under has moved |
| `/api/plugin/table/card?path=&key=` | A hover card: a label and a few fields |

A page’s rows come in the order its query asked for.
Its `reason` says why it is not complete (`PageReason` in `table_source.py`): a scan
that ran out of the request’s budget answers what it found, a sort that could not be
done in the budget answers no rows and names the field in `sort_refused`, and a source
that read only part of its content or a cursor from another generation says so.
`limit` is the rows the page allowed, fewer than asked for when its rows are wide.

Two built-in sources read rows into memory:

- **`delimited`** (`builtin_plugins/delimited/source.py`): a `.csv` or `.tsv` file as
  one table.
- **The structured plugin’s record lists** (`builtin_plugins/structured/records.py`): a
  JSON or YAML file whose top level is a list of mappings as one table, its fields the
  keys typed from their values (plan Decision 12). It reads the structured plugin’s own
  parse (`load_structured_payload`), the one the Tree view made when there is one, and
  without the Tree view’s YAML re-serialization when there is not; any other document is
  refused with `source_unreadable`, saying why.

Both hold a whole file’s rows in memory and answer through the table plugin’s memory
engine (`builtin_plugins/table/memory.py`): the scan, filters, search, sort indexes,
cursors, and single-flight parse cache, behind a `MemoryTable` protocol each source
implements with its rows, sort keys, and cells.
The engine is the built-in sources’ own, not SDK surface.

`tests/test_table_source.py` checks the protocol, `tests/test_delimited_source.py` the
delimited source through these routes, on a served folder and on a Git pin, with the
registry and the doctor’s checks, and `tests/test_record_list_source.py` the record
lists the same way; `tests/golden/cli-api-table.tryscript.md` and
`tests/golden/cli-api-table-records.tryscript.md` pin each route’s answers and refusals.
A file that is its own single table, such as a CSV file, is addressed by its own path.
Tables inside one file, such as a database’s, are its container children
([Navigation Containers](#navigation-containers)): `open_table_source` resolves
`<file>/<table>` through `resolve_content_container` with any extension, classifies the
file, and hands its source the inner path as the table, so a source’s table ids are its
address segments and every route but `tables` answers at the table’s address.
The SQLite source (`builtin_plugins/sqlite/source.py`) answers through reader processes
([Tabular Data Browsing and Live SQLite](../specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md),
The SQLite Source); `tests/test_sqlite_tables.py` checks it, and
`tests/golden/cli-api-sqlite-tables.tryscript.md` pins its answers.
The fsqlite store’s source (`builtin_plugins/fsqlite/source.py`) is that source with an
opener: its file is the store’s marker, and the database it reads is the snapshot the
store’s `current` names, under the store’s generation; `tests/test_fsqlite_store.py`
checks it, and `tests/golden/cli-api-fsqlite.tryscript.md` pins its answers.

**The view.** The table plugin’s `index.js` exports
`mountTable(container, {path, renderJson})`, the table view, which a source plugin
registers as its kind’s Table view through `mb.plugins.load("table")`, as
`builtin_plugins/delimited/index.js` does; the plugin has no kind, so it registers no
view of its own. `renderJson`, the context’s other member, draws a JSON value in a
record: the table plugin requires no other plugin, and the structured plugin requires
it, so the structured kind’s Table view (in `builtin_plugins/structured/index.js`) hands
the table its inline tree rather than the table loading the structured plugin, which
would be a cycle discovery refuses.
That requirement makes the table plugin a root of the built-in plugin graph: `agents`
and `diff` require `structured`, and `event_log` and `unknown_jsonl` require `agents`,
so a table plugin that discovery refused would refuse all of them, and the JSON Tree
view with them. A replacement table plugin that discovery refuses gives the built-in
back, as above, so this widens what one plugin’s refusal would take down without adding
a way for it to be refused.
`table-model.js` holds what the view decides, pure functions of the address, the schema,
and the rows held, and `table-view.js` draws it
([Data Tables](../../design-system.md#data-tables)). `tests/dom/table-view-session.js`
runs both over the routes’ recorded answers, and
`tests/golden/cli-ui-table-view.tryscript.md` pins what it shows.

## Reading SQLite Databases

The built-in `sqlite` plugin claims any SQLite database by a `magic` rule and reads it
as a guest: never writing to it or its log, never creating or removing a file beside it,
never rolling back another process’s journal, and never taking a lock that can refuse
its owner’s commit. The rules are the plan’s
([Tabular Data Browsing and Live SQLite](../specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md#the-sqlite-source))
and the measurements behind them are
[Reading Another Application’s SQLite Database](../../../explorations/sqlite-guest-reads/README.md).

- **One helper.** `src/metabrowser/sqlite_access.py` is the one way the product opens a
  database it does not own, and imports only the standard library.
  `observe` stats the real file and its sidecars and reads their headers; `choose` is
  the access table; `read` runs one short read transaction under it, validating a
  lock-free read against a second look and waiting out a live journal or a failed
  validation until the deadline, or for at most the attempts its caller names.
  `apply_settings`, `bound_work`, and the reads-only authorizer are the connection
  settings, each a named constant there.
  Its errors carry the state the view shows (`ERROR_STATES`).
- **Reader processes.** Every connection runs in a worker of
  `src/metabrowser/sqlite_readers.py`, never in the server, since a handle the server
  closes on a database drops every lock its process holds there.
  A worker is a fresh interpreter that loads only `sqlite_access.py` and the modules
  registered with `register_worker_module`, under a stand-in `metabrowser` package; it
  answers the requests in `sqlite_access.OPS`, one at a time.
  The pool’s size, queue, kill grace, and address-space limit are named constants there,
  with what set them; it creates, removes, and sweeps the private folders where copies
  and Git blobs go.
- **The product’s own databases.** The GitHub plugin’s pull request catalog runs in the
  server process, since it is written there.
  It takes `apply_settings` and `is_database_header` from the helper, and closes every
  handle it opens on the catalog through `PROCESS_HANDLES`, which defers a close until
  the last connection in the process to that file has closed.
- **Evidence.** `tests/test_sqlite_guest_access.py` runs each case of
  `tests/sqlite_guest_scenarios.py` with a real owner in another process, as an
  unprivileged user, and compares the folder before and after;
  `tests/test_sqlite_access.py` checks the access table, settings, authorizer, and pool;
  `tests/test_github_pull_catalog_locks.py` shows the catalog keeps its locks.

## Navigation Containers

### Item-Like and Folder-Like

Every entry in the navigation tree plays one or both of two roles:

- **Item-like:** selecting it opens a document with view tabs.
  A file is item-like, and so is one file’s change inside a patch.
- **Folder-like:** it expands in place to child entries, and selecting the entry itself
  opens an overview of the whole.
  A directory is folder-like, and so is a patch file.

The roles are capabilities, not types.
A patch file is both: a real file with bytes and views, and a set of file changes worth
navigating one at a time.
Nothing in the tree contract asks whether an entry is a directory, only whether it
expands and what selecting it opens.

Directories are the precedent.
Clicking a folder row opens its Overview, the triangle discloses children, keyboard
expansion and lazy child loading work, and selection follows focus.
A container keeps every one of those behaviors, so a design question about containers is
usually answered by what a directory already does.

### Containers

| Container | Children | Selecting the container | Selecting a child | Status |
| --- | --- | --- | --- | --- |
| Directory | Files and folders | Folder Overview | The file’s views | Built |
| Patch or diff file | One entry per changed path | The whole change set | That path’s diff | Built |
| SQLite database | Its tables, views, and virtual tables, at `<database>/<segment>` | An overview of its tables | That table, drawn by the table plugin | Built |
| Commit, `/commit/<rev>` | The commit’s changed files | The commit’s diff | That file’s diff | The child route parses; the panel restores the commit, not the file |
| Archive, such as `.zip` | The archive’s members | A listing or summary | The member’s own views | Planned ([archive plan](../specs/active/plan-2026-11-24-archive-contents-and-browsing.md)) |

The GitHub plugin’s Pulls list and pull-request pages are plugin views over its own
routes, not containers under this contract.

### The Mechanism

A kind declares the folder-like role in its manifest, as the built-in `diff` plugin
does:

```toml
[[kind]]
id = "diff"
match = { exts = [".patch", ".diff"] }
container = { children = "children" }
```

`container.children` names one of the plugin’s own data-hook routes.
For `?path=<container file>` it returns `{children: [{name, path, badge?, muted?}]}`,
where each `path` is the virtual child path.
Three behaviors follow, and no other machinery:

- **The tree** gives such a file a chevron and an empty child group, fetches the
  children on first expansion, and renders them as ordinary item-like rows.
  The server injects `METABROWSER_CONTAINER_EXTS` from kinds matched by `ext` or `exts`;
  a kind matched by content still resolves as a container but shows no chevron.
  The ARIA synchronizer and the arrow-key handlers ask whether a row owns a child group,
  never whether it is a folder.
  Once read, a container’s children follow its file: the tree watches it
  (`metabrowser.watchFile`, [File Watches](arch-live-delivery.md#file-watches)) and
  reads the children again when its generation moves, at once while the container is
  open and on its next expansion while it is closed, keeping the rows drawn until the
  new ones arrive. A database whose owner creates a table is the case this is for.
- **The server** resolves `<container file>/<inner>` in `_resolve_container_child` by
  walking the path’s ancestors through the safe-path gate.
  The nearest existing file whose kind is a container claims everything beneath it, up
  to `MAX_CONTAINER_INNER_DEPTH` in `source.py`; a directory ancestor means the leaf is
  missing, so ordinary 404s are unchanged.
  On a Git revision pin there is no ancestor walk: the contiguous `g1-` segments are the
  container’s `GitPath`, and the rest is the inner path.
- **The views** of that kind receive an envelope carrying `container` and
  `container_inner`. The diff plugin’s document hook answers a virtual path with the
  change set narrowed to that file, so the renderer knows nothing about containment.
  A sidekick resolves the same address with `resolve_content_container`.

The children hook groups by path: a patch spells a type change as a delete and an add at
one path, and two rows with one virtual path would open the same thing.

### What Stays Uniform

- **Addresses:** a child extends its container’s address.
  `/view/changes.patch` is the overview and `/view/changes.patch/src/app.py` is one
  file’s diff, the same shape as `/commit/<rev>/src/app.py`; see
  [Browser URL Grammar](arch-views-models-routes.md#browser-url-grammar).
- **Tree mechanics:** roving focus, `aria-expanded`, lazy pagination, filtering, and
  selection-follows-focus apply to every container.
  Filters filter inner entries like any rows.
- **Expansion state** lives in the DOM, as a folder’s does: a full repaint renders
  containers collapsed, with one bounded refetch on re-expansion, while a filter change
  leaves expanded children in place.
- **Overviews are views,** so they follow the renderer rules: disposal, lazy mounting,
  and measured size bounds.
- **Live updates follow the source:** a directory’s children track the filesystem, and
  an immutable comparison never repaints under the reader.

Re-rooting the tree at a container, the same move as serving a subdirectory, is
proposed: any folder-like entry is a possible root.

### Registration Surfaces Not Built

No plugin can register a router, an address space, a URL reducer, a provider adapter, a
route-backed resource kind, or a navigation panel.
The
[thin-mirror plan](../specs/done/plan-2026-09-23-v012-thin-mirror.md#retired-from-earlier-plans)
set those SDKs aside for v0.12 in favor of the existing reducer hook and plugin routes.
The Commits and Pulls tabs register through `window.MetabrowserShell`, an internal seam
for core modules that is not part of the SDK.

## Adding a File Type

The steps below take a format from unknown to fully supported.
Each is optional except the kind and one view.
A programming language needs only steps 6 and 7, and
[Adding a Language](../../adding-a-language.md) is the recipe for them.

1. **Claim the kind.** Add a `[[kind]]` rule to a plugin manifest.
   An extension or basename is cheapest; a content predicate is for a format that shares
   an extension, at a priority above the built-in rule it narrows.
   The format must reach step 5 of [Classification](#classification), or, for a binary
   format with a magic number, step 6 through a `magic` rule; any other binary format is
   claimed by path with `binary = true`. Check the result with
   `metab . --plugins-dir <dir> --show <file>`, which prints the kind and its views.
2. **Draw it.** Add a `[[view]]` and its `mb.registerView` call.
   The renderer owns its container, returns a disposer, and loads anything large on
   demand, as [Plugin Authoring](../../plugins.md#registration-and-lifecycle) requires.
   A kind with two or more views gives each a key.
3. **Serve structured data,** when the browser should not parse the bytes itself.
   An installed plugin adds a `[[data_hook]]` whose sidekick reads through the content
   reader (`resolve_content`, `read_content_window`), which answers on a folder and on a
   Git pin alike and bounds every read.
   A format whose files are tables declares a `[[table_source]]` instead, and the
   `table` plugin’s routes serve it ([Table Sources](#table-sources)).
4. **Parse a JSONL stream,** when the format is one.
   `register_log_adapter` adds a detector and parser for the JSONL view, and a rule with
   `match = { ext = ".jsonl", adapter = "<name>" }` claims those files, as the `agents`
   built-in does for the Claude Code, Codex, Pi, and Gemini adapters, which register
   from its manifest’s `register` module.
5. **Make it a container,** when its parts are worth navigating, with
   `container = { children = "<route>" }`.
6. **Give it a type family,** so the Files filter, Overview’s type breakdown, the
   Treemap, and file colors and icons group it.
   The File Rollup Format’s definitions live in
   `src/metabrowser/data/file-rollup-format/recommended-file-types.toml`: a family with
   its group and `hue`, and a rollup kind listing its extensions, filenames, and
   shebangs. A rollup kind is not a plugin kind.
   Increment `registry_revision`, regenerate the checked copies with
   `devtools/file_type_contract.py --write`, and run that script without a mode;
   `devtools/check_file_type_colors.py` checks the hue.
   The [format](file-rollup-format/file-rollup-format.md) defines the rules and when a
   change needs more than a revision.
7. **Route its source text.** `file_extensions.py` decides how source text opens.
   An extension with a grammar in the vendored Highlight.js registry joins
   `SYNTAX_LANGUAGE_BY_EXTENSION` (or `SYNTAX_LANGUAGE_BY_BASENAME` for a name such as
   `Makefile`), which also makes it text at any size; a grammar the vendored build lacks
   is vendored first, as `highlight-toml.min.js` is.
   Text with no grammar joins `BROWSER_TEXT_EXTS`, and an image format the browser draws
   joins `BROWSER_IMAGE_EXTS`. `settings.py` sends the registry to the browser, so every
   Source view routes alike.
   `tests/test_file_extensions.py` and `test_plugin_sdk_syntax_token_contracts` check
   the registry against routing and the vendored grammars.
8. **Prove it.** A built-in kind adds a `--show` case to the CLI golden and its
   functional rows, as
   [CLI and Functional UI Parity](../../../AGENTS.md#cli-and-functional-ui-parity)
   requires; `tests/test_plugin_e2e_render.py` fails when a manifest view has no
   `registerView`.

A format whose reader needs a native library belongs in an installed plugin, so its
dependency never becomes Metabrowser’s.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
