# Architecture

Metabrowser is a Python server, a browser shell, and a manifest-driven plugin system.
The package deliberately keeps file navigation, safe filesystem access, live updates,
and plugin lifecycle management in core while delegating file-kind rendering to plugins.

## Runtime Shape

The `metab` CLI starts a Starlette application with four main layers:

1. **Safe filesystem access.** `paths_safe.py`, `gz_io.py`, and the file endpoints
   resolve every requested path beneath the selected root.
   Gzip and zlib files retain their logical extension and can be read transparently
   within shared resource bounds.
2. **Inventory and change events.** `inventory.py` builds a bounded in-memory index.
   Watch backends and the active-file tracker publish normalized changes through the
   event bus and server-sent events.
3. **Plugin discovery and routing.** `plugin_loader/` validates manifests, compiles kind
   classifiers, serves plugin assets, and mounts optional Python data hooks.
4. **Browser shell.** `static/app.js` owns navigation, the tree, recent files, tabs,
   caching, and view mounting.
   `static/plugin_sdk.js` exposes the supported renderer API under `window.metabrowser`.

The browser loads critical local assets first.
Optional third-party assets enhance syntax highlighting, charts, or specialized
renderers after the shell can already paint a useful first view.

The server and the browser shell are one deployable unit, not two independently
versioned peers. The index route is served uncached, `_static_asset_url` stamps every
script with a content-derived `?v=` token, and `client_settings_dict` inlines the
browser’s configuration into that same response.
An upgraded server therefore always serves the matching shell, settings, and built-in
plugins together; a browser cannot pair an old asset with a new route.
This is why internal contracts change in one commit and why compatibility shims between
the two halves are forbidden — see
[Compatibility and Legacy Code](development.md#compatibility-and-legacy-code).

## Request Flow

Opening a file follows this sequence:

1. The canonical `/view/<path>` URL or tree selection supplies a served-root-relative
   path. A URL fragment identifies a location inside that document, never a file.
2. `/api/file` safely resolves the path, determines its logical extension, and runs
   plugin classifiers before built-in fallbacks.
3. The response includes the chosen kind and the ordered view descriptors contributed by
   manifests.
4. The shell creates one container per view and resolves each `(kind, view)` pair in the
   JavaScript registry.
5. The default renderer mounts immediately.
   Other renderers mount lazily the first time their tab is selected.
6. A plugin may render from the file envelope, fetch a KPress view, or call one of its
   declared data hooks.

Replacing the preview pane disposes mounted plugin views.
Switching tabs does not: their DOM and captured state remain available until a different
file replaces the pane.

The built-in Markdown plugin resolves standard relative and leading-slash destinations
exactly from the source document.
It gives internal anchors canonical `/view/` URLs and maps embedded local resources
through the bounded `/raw` endpoint.
Its source-aware Obsidian adapter preserves escaped and code contexts, maps wiki links
to exact paths or completion-aware unique inventory results, and creates stable heading
and named-block anchors before rendering.
Missing and ambiguous wiki targets remain visible; media wiki embeds reuse `/raw`, and
note, heading, and named-block transclusion returns through KPress with shared depth,
document, source-byte, elapsed-time, cycle, abort, and disposal limits.
The plugin also exposes bounded immutable graph analysis through the SDK; visualization
remains outside the resolver.
The shell remains Markdown-dialect agnostic: the plugin intercepts only plain primary
activation through the public navigation SDK, while modifier clicks, new tabs,
downloads, external URLs, and ordinary not-found handling retain browser behavior.
Fragment scrolling runs only after the matching asynchronous Markdown mount completes
and ends with that mount’s disposer.

## Folder Views and Overview Composition

Folder views extend the same request and registry flow to directories.
`/api/file` returns `kind: "folder"`, an ordered set of top-level folder view
descriptors, folder aggregates, and bounded direct-child discovery facts such as
`readme_path`. The served root and selected nested folders use the same envelope and
rendering path.

Folder information is divided by interaction level:

```text
folder
├── Overview                         default top-level view
│   ├── Files                        always-present file-type summary panel
│   ├── README                       conditional document panel
│   └── License and other panels     future plugin contributions
├── Treemap                          peer top-level view
└── Files listing                    future peer top-level view
```

Top-level views answer “which mode am I using?”
and continue to use manifests plus the `(kind, view)` renderer registry.
Overview panels answer “which useful facts apply to this folder?”
and use a separate public panel registry.
A future Files listing belongs beside Overview and Treemap; it does not become a large
panel inside Overview.

The built-in folder plugin owns the Overview composer, but not a hard-coded list of
panels. It publishes the documented `mb.folderOverview` registry facade; built-in and
installed plugins register stable panel IDs with a named placement band, accessible
label, surface or document presentation, bounded resolver, keyed instance mount,
disposer, and print eligibility.
The composer validates descriptors, establishes deterministic order before asynchronous
work finishes, and gives every contribution an independent loading, error, recovery,
abort, and disposal boundary.
A panel never reaches into sibling DOM or private shell state.
The composer also renders every panel label as the same visible `h2` and aligns host
content to the responsive Markdown document boundary.
Each `h2` contains the shared trailing-chevron disclosure button.
Each descriptor declares its initial disclosure state.
Files and README begin expanded; File Breakdown begins collapsed.
Toggling a heading changes only body visibility, so live rollup watches, rendered
Markdown state, TOC state, and keyed panel mounts remain intact.
In Overview, the Markdown mount keeps its ordinary document semantics, TOC, and card.
The card retains its border and shadow at regular and wide document bands, then follows
KPress’s standard borderless narrow layout.
The Files and File Breakdown summaries remain flat chrome sections; their edges follow
the README card when present and the README prose edge when the card collapses.

Core supplies only generic contribution-registry, resource-context, request, formatter,
and view-state primitives.
The folder plugin supplies the folder-panel schema and registry facade.
A plugin owns its panel’s domain data, optional data hook, renderer, and styles.
The visible **Files** heading belongs to `folder.file-totals`. It renders the shared
Files / Bytes chooser and the inventory-backed Files and Ignored tallies without waiting
for the detailed rollup.
Each row is its own complete population: Files means unignored files and Ignored means
excluded files. A nonzero row therefore has a full-width composition track and no
percentage label. The visible **File Breakdown** heading belongs to the stable
`folder.file-types` panel ID. It renders the shared Show ignored checkbox and the
rollup-backed type table using the packaged recommended definitions from File Rollup
Format v0.1. Both panels observe one folder-rollup state, so the chooser in Files
updates both panels and Treemap without a duplicate chooser in File Breakdown.
File Breakdown owns the only Overview rollup watch and publishes each validated terminal
envelope through a ref-counted, per-directory projection pool.
Files subscribes to that projection and uses the same palette pool, which adds
composition detail without a sibling DOM dependency or another request.
Rollups aggregate every known family and its complete canonical children before
independently bounding only No extension basenames and Other types extensions.
The comparison table follows registry order across Code, Documentation, Data, Archives,
Media, and Other; Log files is a semantic family within Other.
Every nonempty family can disclose exact extension rows, including a family with one
contributing extension, without adding group subtotals.
No extension discloses exact basenames and Other types discloses raw extensions; both
cap at 20 children and conserve their omitted values in an exact Others row.
Each File Breakdown row renders the selected count or byte share as an inline bar beside
its exact value and percentage.
The two-row Files summary always leads with unignored Files and follows with Ignored.
The rows are disjoint and conserve the complete directory population.
Each composition track normalizes its own row to 100% and segments it by the same
top-level semantic file-type families shown in File Breakdown.
Segment order also matches File Breakdown: registry group order first, then descending
selected-metric value within each group for the active Show ignored scope.
Both tracks use this one order so Files and Ignored remain directly comparable.
Hovering a segment uses the shared body-portaled navigation tooltip with the semantic
family name in bold and its exact disjoint-population file count and byte size below.
The whole Ignored row uses the shared dimmed-content opacity applied to ignored
navigation and Treemap entries.
README is another contribution whose resolver checks the folder envelope and whose
renderer delegates to the instance-safe built-in Markdown mount.
Using the same mount keeps Overview’s README structurally and behaviorally aligned with
the ordinary rendered Markdown view instead of creating a second Markdown rendering
path. Inside either Markdown mount, Frontmatter and Diagnostics remain native `details`
disclosures, use the same trailing-chevron design, and begin closed.

Treemap consumes the same bounded rollup as a peer view but has one fixed spatial model:
`treemap_layout.js` packs directory children, recurses only into sufficiently large
folder cells, and conserves any culled or capped tail in a neutral remainder cell.
The renderer flattens parent and descendant rectangles into positioned siblings;
geometry expresses containment, while hover leaves their paint order unchanged.
Its pure model persists only the Bytes/Files metric and the boolean ignored-file scope;
the controller renders those through the shared segmented-control and labelled-checkbox
primitives. The scope selects total or unignored rollup weights without another fetch.
Layout geometry also derives bounded label and value sizes and reserves the resulting
folder-header height before nesting children.

Treemap and File types acquire leases from the same per-directory category-palette pool.
File cells and folder `dominant_ext` values pass through the catalog’s
`distributionKeyForExtension` helper, so known members share a stable `family:<id>` key;
raw extensions remain exact and remainder cells use the neutral Other key.
This shares semantic identity without coupling either renderer to sibling DOM. Visible
byte and file values route through the public SDK formatters.
File cells and exact extension rows also resolve their icon and subtype class through
the public `fileTypeIcon()` SDK helper, the same matcher used by navigation.
The shared `.file-identity-icon` primitive owns their geometry and subtype color.
File cells use ordinary `mb.navigation.open({ path })` navigation; folder and parent
navigation pass Treemap as the optional preferred destination view.
The shell activates that view only when the destination declares it and otherwise uses
the destination’s default.

The folder-view shell refreshes a selected folder envelope for live aggregate header
data. That one multiplexed refresh is exposed through a supported subscription so
Overview can re-resolve panel availability when direct-child facts change without
starting one folder request per panel.
Aggregate panels retain their own bounded watchers when their data plane differs, and
every subscription ends when the selected path is replaced.

Tree disclosure and folder navigation share one row-activation path.
The activation selects the folder and starts its ordinary `/api/file` request while
synchronously toggling the row’s direct-child container.
Repeated activation can therefore collapse the tree branch without changing the selected
folder or replacing its Overview.

Overview exists even when no optional panel applies.
File types remains mounted for a complete empty folder and renders an explicit
zero-total state without bars, a table, or a synthetic README region.
Pending inventory remains a progress state, so an incomplete scan cannot be mistaken for
an empty folder.

## File Rollup Format

`data/file-rollup-format/recommended-file-types.toml` is the reviewed declaration for
classifier kinds, display families, display groups, analyzer content families, and
metadata evidence. `file_type_registry.py` parses and validates it once into immutable
Python values. The server injects the matching immutable JSON projection into browser
settings; `static/file_type_taxonomy.js` supplies the same public classification helpers
to navigation, Overview, Treemap, and plugins.
The generated conformance corpus runs against both implementations, so a file cannot
quietly change family between the server and browser.

Inventory entries retain observations rather than registry-derived presentation:
basename, a normalized logical extension of at most two components, apparent bytes, and
ignore state. `inventory_rollup.py` classifies those facts against the active registry
while building a response.
It emits exact `all` and `unignored` populations for files and bytes, the definition
registry identity, and the current file-rollup hierarchy.
A breakdown is rejected when its registry identity differs from the loaded projection or
when any root, family, fallback, or Others conservation invariant fails.

This boundary deliberately avoids persistent classification caches in the inventory.
A registry revision changes one immutable loader value and subsequent rollups rather
than requiring every indexed entry to be rewritten.
The rollup response carries exactly one representation of file types; a definition
change updates the server, the browser, and the tests together rather than adding a
parallel shape. The reusable semantics, recommended type definitions, schemas,
conformance cases, and export boundary are documented in
[File Rollup Format v0.1](project/architecture/file-rollup-format/file-rollup-format.md).

## Plugin Boundary

Core knows only generic capabilities and built-in file kinds.
It does not contain consumer-specific schemas, endpoint routes, view identifiers, or
renderers. Transparent compression is a core filesystem capability because it applies
uniformly before classification and rendering.
Specialized binary stores and their value schemas belong in separately installed
plugins.

Plugins own:

- classification rules for their domain formats;
- view declarations and labels;
- browser rendering and plugin-specific styles;
- optional extra scripts and styles;
- optional server-side extraction through declared data hooks.

The stable browser-side boundary is the `window.metabrowser` API. Plugins should not
reach into variables or functions defined privately by `app.js`. Cross-view navigation
uses `navigation.open({ path, query?, fragment? }, { viewId? })`; the optional `viewId`
preserves a working mode when the destination offers that view without changing resource
identity or history semantics.
`navigation.href()` supplies canonical `/view/` links, and `navigation.current()`
exposes the selected target without leaking shell state.
Plugin HTTP calls use `fetchPluginData`.

## Browser URL Grammar

A `/view/` URL answers three separate questions, and each component answers exactly one:

| Component | Question | Owned by |
| --- | --- | --- |
| Path | Which content is selected | The served tree |
| Query | How it is presented | The link author |
| Fragment | Where inside the rendered document | The document |

Path and fragment are implemented.
The query slot is currently carried verbatim and never interpreted: it exists so a query
an author wrote, such as GitHub’s `?plain=1`, survives resolution unchanged.

That makes the query the one component with two authorities in it, so it is the one
component that needs a reserved namespace.
**Metabrowser reserves query keys beginning with `_mb_`**; every other key belongs to
the document and is passed through untouched.
Reserved keys are `snake_case`, matching this server’s existing query parameters such as
`include_ignored` and every key on the JSON wire.
Plugins must not read or write `_mb_` keys except through the navigation SDK.

```text
/view/docs/guide.md?_mb_view=source&plain=1#setup
                    └── reserved ──┘ └ doc ┘
```

The seam holds under one invariant, which any future parameter must preserve:

> Removing every `_mb_` key from a URL yields exactly that content’s canonical URL.

The prefix carries two signals because each one alone is ambiguous here.
A leading `_` is the familiar mark for a reserved system field, but this codebase
already spends a bare `_` on the opposite meaning: `/_debug/tasks` and Python privates
mark surfaces that are deliberately not a contract, while view parameters are a
documented surface people bookmark and share.
Adding `mb` names the owner and removes that clash.
Keeping `_` as the only separator also matches the `snake_case` keys, where a dotted
prefix such as `mb.folder_overview` would mix two separators in one name and invite the
occasional tooling that rewrites `.` in query keys.
Parameters elsewhere need no sigil because they are namespaced by route: every key on
`/api/*` is unambiguously the server’s, and only `/view/` shares its query with a
document.

Three rules keep the namespace honest as entries are added:

- A key is reserved only when the **sender** should decide it for the recipient.
  Viewer-owned settings such as theme and reading font stay in host-only cookies;
  putting them in a link would override a choice the recipient made deliberately.
- Reserved keys are sorted for one canonical spelling, but a key is never dropped for
  matching a default. Defaults are viewer-dependent, so an omitted key means “viewer’s
  choice” while a present one means “pinned”.
- An unrecognized `_mb_` key is a visible diagnostic, never silent and never passed
  through as document metadata.

Planned entries are tracked with their features rather than reserved in advance;
[the extensions plan](project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md)
maps the first of them.

## Startup and First Paint

The CLI binds before beginning expensive recursive work.
Inventory walking, ignore-file parsing, and watcher setup run without blocking the event
loop’s first response.

When a `/view/` URL names an initial file, `/api/file` begins independently of tree
indexing. `/view/` selects the served root, and the bare `/` URL is not a second landing
view: it redirects there with a temporary 307 so the served root has exactly one URL.
URL fragments identify document locations and never file paths.
The root folder’s default Overview replaces the former server-picked initial README,
which remains reachable as an ordinary file view.
Inventory endpoints return current partial state plus progress metadata instead of
waiting for a complete walk.

The CLI opens a browser only after the canonical route returns an HTTP success response.
A free TCP port alone is not considered ready, and neither is a redirect, so every
startup URL the CLI prints, probes, and opens is a `/view/` route rather than the
redirecting origin.

## Live Update Model

The inventory is the server-side source of truth.
Producers attach generation-aware write tokens so an observation made before
invalidation cannot overwrite newer state.
The event stream carries snapshot, change, and resynchronization events.

Inventory entries have three shapes: directories, regular files, and symbolic links.
A symbolic link is always a typed leaf, even when its target is a directory: walkers do
not follow it, directory child containers are never created for it, and file aggregates
exclude it. A live upsert may replace any shape with another at the same path, so both
the index and browser remove the old shape before installing the new one.

Regular files receive one logical extension from `fs_paths.derive_ext` at their shared
walker/watcher construction boundary.
The value retains at most the final two eligible suffix components: `bundle.js.map` and
`archive.tar.gz` keep `.js.map` and `.tar.gz`, while `bundle.umd.min.js.map` and
`types.d.ts.map` become `.js.map` and `.ts.map`. A component must be lowercase,
alphanumeric, nonempty, and bounded in length; dotfiles remain extensionless.
The fixed component cap prevents filenames from creating an unbounded vocabulary in
navigation and rollup tallies while preserving common compound formats.
Browser consumers use the indexed value instead of reparsing the full filename.

The browser keeps a normalized file store.
Tree panels and recent-file views subscribe to that store rather than maintaining
independent copies.
If a client falls behind the bounded event buffer, it reconnects with
exponential backoff and requests a fresh snapshot.
Backoff resets only after the replacement connection remains stable, which prevents an
overloaded subscriber from creating a reconnect loop.

## Where Filtering Happens

Navigation filtering is split across two tiers, and which tier owns a dimension is a
consequence of where the information lives rather than a preference.

**Client, over rendered rows.** Type, size, and gitignored visibility are decided in the
browser by walking the rows already in the DOM. Every predicate input — extension, byte
count, gitignore flag — is on the row before any filter runs, so this costs one pass and
no round trip, and it stays responsive while the user toggles.
Its ceiling is what has been rendered: a collapsed subtree is unknown, so the pass keeps
those folders and reports how many it could not speak for.

**Server, as the source of the tree.** Recency is different.
`/api/recent` scans the whole inventory rather than the loaded subtrees, which is the
one thing a DOM walk cannot do, so setting a recency window swaps the panel’s data
source instead of decorating it.
Gitignored visibility rides along as a request parameter because it changes what the
response cap is spent on, not just which rows are painted.

The category, family, canonical-extension, and raw tallies behind the type menu come
from one complete-index pass too.
The Quick File catalog excludes gitignored entries and a menu built from it would
undercount everything the tree still shows.
The chooser orders broad categories, present semantic families, and canonical/raw
children as distinct tiers; all selections use the same longest-declared-suffix
predicate as the rollup.

### Response Caps Are a Ranking Problem

Any server-side filter that caps its response has to decide what to drop.
Newest-first alone is not enough: a dependency install touches thousands of files at
once, so a 2 000-row cap on a day window can be entirely `node_modules` while none of
the user’s own work appears.
`collect_recent_entries` therefore drops gitignored files before tracked ones and
re-sorts the selection, and reports `total_matching` and `truncated` so the client can
say what it is not showing.
Treat that as the rule for any future filtered endpoint: decide the priority order
before the cap, and report the shortfall.

### Moving More Filtering Upstream

Client-side filtering is bounded by what is rendered, so a very large directory reaches
a point where the honest answer needs the index.
The tiers are not fixed, and the vocabulary was built so a dimension can move without
changing what it means: `FilterState` holds the values, and the predicate helpers are
shared, so a dimension evaluated server-side still has to agree with the same
definition.

Worth understanding before moving anything:

- **What server-side filtering buys.** Completeness — an answer over the whole index
  rather than the expanded subset — plus the ability to filter what was never loaded,
  and aggregates that reflect the filter rather than the whole tree.
- **What it costs.** A round trip per change, so a control that felt instant becomes
  latency-bound; cache keys multiply by the filter combination; and every dimension
  evaluated in two places is a chance for the two to disagree.
- **Which dimensions are natural candidates.** Extension and size are cheap index
  predicates and compose with the existing recency scan.
  Activity is not: the tracker’s live set is small, client-held, and already complete.
- **The rule of thumb.** Move a dimension upstream when its client-side answer is
  *incomplete*, not when it is slow.
  Incompleteness is a correctness problem and the user cannot see it; slowness they can.

Two things should stay true whichever tier owns a dimension: with no filters set the
rendered DOM is unchanged from an unfiltered render, and any filter that cannot see the
whole tree says so rather than implying completeness.

## Caching

File responses use stable ETags derived from file metadata.
Expensive projections use mtime-aware caches whose keys change when file size or
modification time changes.
Changing the served root clears root-scoped caches.

Plugins should keep domain caches on their own side of the boundary.
Core provides no global plugin payload cache.

## Package Layout

```text
src/metabrowser/
├── builtin_plugins/   # Built-in manifests and renderers
├── cli/               # serve, remote, walk, and plugins commands
├── logutil/           # Generic agent-log normalization
├── plugin_loader/     # Discovery, manifests, classification, and routes
├── static/            # Browser shell, SDK, charts, icons, and styles
├── inventory.py       # In-memory filesystem index
├── server.py          # Starlette application and HTTP endpoints
└── watch_backends.py  # Filesystem change producers
```

Tests mirror these layers.
Node `vm` shims validate browser-side plugin registration without adding a full DOM
dependency, while Python integration tests exercise the real application lifespan and
route stack.

## Related Documentation

- [Security policy and content trust model](../SECURITY.md)
- [Plugin authoring](plugins.md)
- [Design system](design-system.md)
- [Folder Overview panels and file-type summary](project/specs/done/plan-2026-08-12-directory-file-type-summary.md)
- [End-to-end testing](e2e-testing.md)
- [Real-time debugging](realtime-debugging.md)
- [Development](development.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
