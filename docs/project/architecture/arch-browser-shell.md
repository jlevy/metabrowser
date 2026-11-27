# Browser Shell

**Status:** Built: the shell’s modules and stores, the preview pane’s claims and staged
handoff, Quick Search over files and cached pull requests, and three asset loading
tiers. Planned: full-text search and a bounded server filename search
([Quick Search plan](../specs/active/plan-2026-07-17-scalable-file-search.md)).

The shell is the one page every address serves: `static/app.js` and the modules it
composes, written as plain scripts with no build step and served by the running server
build.
Plugins reach it only through `window.metabrowser`; how plugins are discovered and
classified is in [Plugin System](arch-plugin-system.md).

## Modules

`app.js` composes the tree, Recent, the filter bar, the file cache, the preview pane,
the live JSONL stream, the inventory event stream, and the settings menu.
The modules beside it each own one subject, and most expose one `window.Metabrowser*`
global. Those globals are internal: the shell and the built-in plugins, which ship with
it, may read them, and an installed plugin uses the SDK.

| Area | Modules |
| --- | --- |
| Loading and the SDK | `asset-loader.js`, `plugin-sdk.js`, `plugin-sdk-views.js`, `perf.js` |
| Navigation and the pane | `navigation.js` (routes and the pane’s claim lifecycle), `view-composition.js`, `view-header.js`, `view-state.js`, `nav-collapse.js` (hiding the navigation pane) |
| Stores | `resource-context.js`, `directory-totals-store.js`, `inventory-scope.js`, `known-file-catalog.js`, `catalog-feed.js` |
| Tree and filters | `tree-expansion.js`, `tree-keyboard-navigation.js`, `tree-filter-model.js`, `filter-state.js`, `filter-controls.js`, `pending-tally-diagnostics.js` |
| Main tabs | `main-tabs.js`, `git-panel.js` with `git-graph.js` and `git-history-window.js`, `pulls-nav.js`, `pull-route.js`, `refresh-plan.js` (the navigation’s one Refresh, which refreshes every tab’s part, those on screen first) |
| Keyboard and dialogs | `keyboard-shortcuts.js`, `shell-keymap.js`, `plugin-shortcuts.js`, `key-reveal.js`, `keyboard-help.js`, `overlay-layer.js`, `menus.js` (how every menu closes) |
| Quick Search | `search-controller.js`, `search-palette.js`, `file-fuzzy-match.js` |
| Pinned revisions, mirrors, and a checkout’s revisions | `git-path.js`, `revision-ages.js`, `source-pin-guard.js`, `source-freshness.js`, `source-ref-selector.js`, `mirror-heading.js` |
| Shared rendering | `formatters.js`, `icons.js`, `charts.js`, `file-type-taxonomy.js`, `inert-html.js`, `source-append.js`, `theme-state.js`, `document-width.js`, `request-error.js`, `contribution-registry.js` |

`types.d.ts` declares the globals and the SDK. `tsconfig.json` type-checks every module
strictly except a listed legacy set, which `tsconfig.legacy.json` checks;
[AGENTS.md](../../../AGENTS.md#browser-and-plugin-boundary) keeps new modules under the
strict gate. `window.MetabrowserShell` is the narrow internal seam through which
`git-panel.js` and `pulls-nav.js` register their tabs and claim the pane, kept out of
the SDK on purpose.

## Startup

1. The server writes the shell (`server.py`): inline `METABROWSER_SETTINGS`, the source
   kind, the repository context, the first tree rows, and the asset bundles, then the
   eager script tags in order, with `app.js` last.
2. `app.js` paints the server-carried rows at once, before `DOMContentLoaded`.
3. On `DOMContentLoaded` it fetches the tree, then starts navigation to the addressed
   view; when that settles, it dispatches `metabrowser:first-view-settled`.
4. Behind the first tree request, `initDeferredShellTools` loads the `shell-tools`
   bundle and attaches the main tabs, the keyboard, Quick Search, and the Commits and
   Pulls panels, then marks the root `data-shell-tools-ready`.
5. `startInventoryEventStream` opens `/api/events`, which carries tree changes and the
   Quick Search catalog’s deltas; [Live Delivery](arch-live-delivery.md) covers events
   and recovery.

## Stores

| Store | Holds | Readers |
| --- | --- | --- |
| File store (`fileStore` in `app.js`) | One normalized entry per path from the event stream’s snapshots and changes | Tree rows, Recent, activity badges; private |
| `directory-totals-store.js` | Directory totals, applied before each event batch is announced | Folder views, through `mb.directoryTotals` |
| `resource-context.js` | One live envelope per path, refreshed once per intersecting change | Folder views, through `mb.folderContext` |
| `known-file-catalog.js` | Quick Search candidates: path, basename, logical extension | Quick Search; plugins, through `mb.fileCatalog` |
| File cache (`fileCache`, `fileETags` in `app.js`) | Bounded file envelopes, revalidated by ETag | File selection and hover prefetch |
| `filter-state.js`, `tree-filter-model.js` | The navigation filter and the presentation tree it yields | The tree, Recent, and the filter bar |

Each store owns its bounds and invalidation, and a plugin reads one only through its SDK
projection, never `app.js`’s variables.

**Filtering** decides membership over the server’s inventory, never over rows mounted in
the DOM. `/api/tree` takes type, recency, size, and ignored-file constraints and answers
the matching leaves with their folder ancestry, so a collapsed or paged subtree is
unknown only to the renderer.
When a recency window hides older files, the panel switches to `/api/recent`, whose flat
newest-first leaves pass the same other constraints, and `tree-filter-model.js` clusters
them before the tree draws them.
Live events are rechecked against the filter between those fetches, but they never
decide a folder’s membership or counts.

## The Preview Pane

### Claims

The tree, the Commits panel, and the pull-request page all draw into one pane.
`claimPreview(owner, selection)` takes the next generation from
`createPreviewPaneLifecycle` in `navigation.js`; every asynchronous producer checks its
claim before each write, so a later selection makes older writes harmless.
A claim also retires the Commits panel’s and pull-request page’s pending work, whose
visible content stays until the replacement is ready.
`navigation.js` owns the claim and placeholder state, so the browserless session
`tests/dom/preview-pane-state-session.js` drives exactly what the shell paints.

### Staged Handoff

File-to-file navigation keeps the previous useful surface visible while the next one
prepares. `renderFile` creates a staging subtree with `createFilePreviewStage`:
absolutely placed, transparent, `inert`, and `aria-hidden`, inside the live pane, so a
renderer gets a connected container and may measure and observe.
The stage is not an interactive or accessible view, so a renderer scopes its DOM and
events to its container and does not move focus while rendering.
When the active renderer’s render promise and optional `ready` promise settle, the shell
moves the staged content and its disposers into the pane in one step.
If navigation moves on first, the shell runs the staged disposers at once, disposes a
late handle when it arrives, and never lets that mount regain the pane.
Nondefault tabs still mount lazily, on their first selection.
The staged tab bar takes a choice from the moment it is drawn, before the hold: a tab
chosen during it, by a click on the staged bar or by name (`showPreviewTab`), mounts
then, and the commit brings it to the front in place of the first view.
A view asked for by name before the stage exists is the view the render opens in, and a
tab picked on the bar the reader sees reaches the stage only when the stage is the same
file’s, as Load more’s render is.
The tab functions are the compositor’s (`bindTabs`, `selectTab`, `setActiveView` and
`stagedFile` in `view-composition.js`), which reach a host’s own views only, since a
stage sits inside the pane.
`tests/dom/view-tab-hold-session.js` runs these orders against the production functions.

### Composition and Disposal

`view-composition.js` prepares a kind’s views, loads the plugins that declare them, and
owns the disposer list.
`createLifecycle().begin()` returns a stage that is either cancelled, disposing
everything it collected, or committed, after which lazily mounted tabs join the active
list. Replacing the pane disposes that list, and `releaseShortcutsWithin` releases any
plugin key still attached inside the container.
The same module runs in the browserless sessions in `tests/dom/`.

`view-header.js` builds the header `renderFile` draws above a file’s or a folder’s views
([View Headers](../../design-system.md#view-headers)) over helpers `app.js` passes it,
so its sizes, counts, ages, and icons are the tree rows’ own.
It is an on-demand bundle, not a startup script: `loadViewComposition` fetches it beside
the compositor and the SDK’s view helpers, and a header is drawn only after that.
The server comment on its bundle in `server.py` records what it costs.

A retained pull-request page goes through `cancelPending()` first: its subtree turns
inert while the next view prepares, and `dispose()` follows the actual replacement.

### Plugin Assets

The server writes `MetabrowserPluginHost.configureAssets` with each plugin’s assets by
name and the plugins each kind’s views come from (`_build_plugin_asset_config_block`),
so no plugin asset is a startup dependency.
The first selection of a kind, or a call to `ensureKindAssets`, loads its plugins once:
styles in parallel, then extra scripts in manifest order, then `index.js`.
`metabrowser.plugins.load(name)` shares that load and resolves to the plugin’s
`index.js` exports, which is how a plugin reaches a provider it declares in `requires`,
and how a plugin with no kind of its own is reached at all.
[Plugin Authoring](../../plugins.md#plugin-asset-lifecycle) states the guarantees a
plugin relies on.

## The SDK Boundary

`window.metabrowser` is defined by `plugin-sdk.js`, eager, and extended by
`plugin-sdk-views.js` with the view-phase helpers before any plugin code runs, by
`filter-controls.js` with `filterControls`, and by the built-in folder plugin with
`folderOverview`. A plugin’s helpers for other plugins are its module’s exports, which
`plugins.load` answers, never a property of this object.
[Plugin Authoring](../../plugins.md#browser-sdk) documents it.

Its `navigation` is `navigation.js`’s facade.
`open` applies a `/view/` target through the shell’s navigation controller, and
`openRoute` opens any other in-app page a link names, a pull request’s, a stack’s, the
list’s, or a commit’s, in place: the tab controller (`openRoute` in `main-tabs.js`)
pushes the link’s address and lands it as a tab’s button lands its destination, the pane
showing what the address names, the tab that holds it in front, and its panel revealing
the item. The facade is one eager line that asks the controller, which arrives with the
shell tools; until then it answers false and the browser follows the link.
`enhance` in `repository-links.js` falls back to it for every route a page does not open
itself, so no surface’s link to such a page loads the page again.

It is also the one console entry point, so diagnostics extend it instead of adding
globals:

- `metabrowser.perf` is the [performance recorder](../../web-performance-framework.md),
  with `report()`, `responsiveness()`, `copy()`, `download()`, and `reset()`; plugins
  may add stable labels through `perf.measure` and `perf.measureAsync`.
- `metabrowser.debug`, from `app.js`, holds `clearFileCache(path?)`, `selectFile(path)`,
  and `pullPage()`, and `metabrowser.bench` exists only once the serving benchmark’s
  probe, `devtools/bench-browser-probe.js`, is evaluated.
  Both are for a person at the console, not for plugins.

## Markdown

Every rendered Markdown document on the page, folder README panels and transclusions
included, shares one lazily built preprocessing Worker, and what an authored link names
is decided by resolvers that do no I/O. `markdown-worker-client.js` documents the
Worker’s references, lanes, and failure, and `enhanceRenderedLinks` in
`link-enhancer.js` the order the resolvers run in, both under
`builtin_plugins/markdown/`.

## Quick Search

`T` or `/` opens a keyboard-first palette that finds files under the served root and, on
a GitHub repository, cached pull requests.

- **Controller:** `search-controller.js` registers providers and owns the query
  lifecycle with no DOM: a new query aborts the last, and a late batch for an old one is
  dropped. A `fallback` provider runs only when the `immediate` results are empty and
  incomplete, or a surface asks for complete coverage; every provider registered today
  is immediate. A batch reports `complete` for its candidate universe and `truncated` for
  its result list, never one inferred from the other.
  Results group by kind, files first, so a later pull-request batch appends below the
  rows already painted.
- **Files:** the local provider fuzzy-matches the catalog snapshot in
  `file-fuzzy-match.js`, scanning a large catalog in chunks that yield to the event loop
  and keeping a bounded top set.
  Ranking is a named vector, exact basename first, then boundaries, contiguity, gaps,
  depth, and a code-unit path tie-break; `tests/fixtures/file_fuzzy_ranking.json` is its
  review surface.
- **The catalog:** `known-file-catalog.js` holds every non-ignored file.
  `catalog-feed.js` fills it from one gzipped `GET /api/catalog` and keeps it current
  with `catalog.change` events on the existing stream: it buffers deltas, applies the
  bulk, then replays them, which converges because operations are idempotent by path.
  It refetches when delta continuity is lost, and a walk that finishes after a reconnect
  triggers one authoritative refetch before the catalog reports complete.
  On a pinned revision the catalog is the blob set and complete at once.
- **Pull requests:** a query starting with `#` searches pull requests alone; a number
  matches a number prefix, and words match titles as case-insensitive substrings.
  The provider debounces an abortable request to the GitHub plugin’s `pulls` route,
  which reads the cached catalog and never calls GitHub while typing.
- **Opening:** a file opens through `navigateToPath`, after forcing its ETag
  revalidation. A file that no longer exists is removed from the catalog and the palette
  stays open to say so; a pull request opens at its Conversation tab.
- **The palette:** a labelled dialog with a combobox, a listbox, and a polite status
  region, mounted outside the tree and the pane so a repaint cannot discard it; `Escape`
  restores the focus it took.
  It changes no filter, preference, or tree state.

## Asset Loading Tiers

Every browser asset has a loading tier, chosen from what the asset costs, not from what
is convenient to write.
Parse and evaluation are paid on load whether or not anything uses the code, so a
library in the eager path costs every reader on every page, and a request count does not
show it.

- **Eager:** a blocking `<script>` in the shell, for code without which the first render
  is wrong. The shell template in `server.py` lists them, and the list stays small.
  `PIN_STARTUP_SCRIPTS` and `PULL_PAGE_STARTUP_SCRIPTS` add one script each to a pinned
  revision’s shell and a pull-request address’s shell, which the startup check reports
  beside the budget without gating.
- **Prefetched:** fetched after first paint, when the page is idle and before anything
  asks, for code that is small relative to how likely it is to be wanted and visibly
  late otherwise. Mustache, then Highlight.js, start through `whenIdle` with
  `PREFETCH_IDLE_TIMEOUT_MS` as the ceiling; a plugin that needs Mustache sooner demands
  the same `mustache` bundle, so it loads once.
  A pull request’s page whose description carries a guide prefetches Guided Review’s
  module, `builtin_plugins/github/guided-review.js`, with the guide’s first step, and a
  stack’s page with a guide does too (`readGuideAhead` in `pull-page.js` and
  `stack-page.js`; the cost is in `guide-reads.js`).
- **On demand:** fetched the first time something needs it, for code that is large,
  narrowly used, or both: the bundles in `on_demand_script_bundles` in `server.py`.
- **Inline, page-specific:** written into the shell of the pages that use it and of no
  other, for small code only those pages need before their first paint:
  `mirror-heading.js` on a served mirror’s page (`_mirror_heading_script` in
  `server.py`, read from disk once).
  A plain folder pays nothing for it, but a page that has it pays its bytes in its HTML,
  outside the startup-script gate’s count of requested scripts.
  A github.com checkout’s shell also carries more in its HTML than a plain folder’s, its
  repository context and the Git tabs, so `devtools/check_startup_scripts.py` reports
  how much more the application sends for it, beside the budget, without gating it.
  The View on GitHub button is in the on-demand view helpers
  (`static/plugin-sdk-views.js`), which every page that draws one has loaded by then.

Data follows the same rule: a bulk payload one surface reads is on demand.
A pull request’s page prepares the initial Changes comparison, which its header’s Diff
summary reads on every tab, and the diff plugin’s modules;
`builtin_plugins/github/comparison-prefetch.js` records what that costs.

### The Loading Mechanism

A library that installs a global loads through `asset-loader.js`. The server publishes
the bundles as `METABROWSER_ASSET_BUNDLES`, and `ensureAsset(name)` appends a bundle’s
scripts in order, since a Chart.js plugin is inert without `Chart`. A loaded set and an
in-flight map make concurrent callers share one load.
A bundle can instead be one ES module, `{module: url}`, for a library whose build
imports its own parts by relative specifiers: `ensureModule(name)` imports it once and
resolves to its namespace, and the browser fetches only the parts a caller reaches.
Mermaid is one, and its chunks are fetched unstamped beside the stamped entry, and
answered immutable all the same, because each one’s name is a hash of its content
(`_SELF_NAMED_STATIC` in `server.py`). KPress’s diagram renderer and controls are two
more, `kpress-diagrams` and `kpress-diagram-controls`, published at the stamped URLs a
render’s manifest names, so they share the document’s one KPress runtime.
KPress loads through `loadKpressAssets` in `static/plugin-sdk.js` instead: its
stylesheets first, then the import map the KPress asset manifest carries, when it has
one, then the manifest’s module and classic entry points as scripts, with its
table-of-contents module through dynamic `import()`.

Moving a library off the eager path needs an absence contract at every consumer: a guard
that skips a missing global becomes one that awaits the loader, and late arrival
re-enhances what is on screen through `metabrowser:optional-asset-loaded`.

### Idle Work

`metabrowser.whenIdle(callback, {timeout})` in `plugin-sdk.js` is the one way the shell
and built-in plugins schedule work for when the page is free, and it returns a
canceller. `tests/test_idle_work_js.py` fails on any other `requestIdleCallback` call.
Where the engine has `requestIdleCallback`, the helper is that.
The macOS app’s `WKWebView` has none (measured on macOS 26.5.2 on 2026-11-11; WebKit bug
285049), so there the helper waits for `metabrowser:first-view-settled` and then for
`IDLE_INPUT_QUIET_MS` with no `pointerdown`, `keydown`, or `wheel`. A `timeout` bounds
the whole wait. Untimed work waits for the first view however long it takes, as
`tests/dom/idle-work-behavior.js` pins, because the one untimed caller, a pull request’s
comparison prefetch, would otherwise compete with a view still drawing.

The same engine lacks the `longtask`, `long-animation-frame`, and `layout-shift`
observers, so `cls` stays null there, and `perf.responsiveness()` reports
`raf_frame_gaps` instead of Long Tasks: frame intervals over `FRAME_GAP_MS`, the Long
Tasks threshold, sampled for `FRAME_SAMPLE_WINDOW_MS` after load, `reset()`, and each
trusted click or key.
A gap is a frame not drawn, not a measured task, so it never fills the Long Task fields.

`IDLE_INPUT_QUIET_MS` equals the tree’s hover prefetch delay,
`FILE_PREFETCH_HOVER_DELAY_MS`, longer than a held key’s repeat or a wheel’s event
interval, and `FRAME_SAMPLE_WINDOW_MS` covers a transition and its settling.
Both were chosen, not measured in `WKWebView`, which needs the probe the
[native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md) names.
Their files are startup scripts, so this section holds what their comments would say.

### Justifying a Tier

State the measurement, taken in a real browser against a real corpus, as
[rendering large content](../../large-content-rendering.md) requires for size limits,
and record it beside the constant that makes the decision.
`startup_script_requests` and `startup_script_transfer_kb` in
[`performance-budgets.toml`](../../../explorations/performance-loop/performance-budgets.toml)
bound the eager tier, and `devtools/check_startup_scripts.py` applies both on every
`make lint-check`: it renders a folder’s shell, compresses each script as the gzip
middleware does for a client it gzips for, and runs the shell’s scripts browserlessly
(`tests/dom/shell-startup-requests.js`) to fail on any script one of them requests
before `DOMContentLoaded`. When it fails, move code out of a startup script or behind
the first usable tree; raising a ceiling needs a measurement showing the headroom is
real. A server started for local use sends a loopback browser its scripts uncompressed,
so `run.py record` reads the gate’s number from the scripts as the remote path sends
them; the note beside the budget says why.

| Asset | Tier | Decided at | Measurement |
| --- | --- | --- | --- |
| Core shell modules | Eager | The shell template’s script tags in `server.py` | The note beside the startup gates in `performance-budgets.toml` |
| Search, Help, keyboard, Git, Pulls, and Refresh tools | On demand, once the first tree is usable; Pulls only in a shell that drew the tab | `shell-tools` in `on_demand_script_bundles` | The same note |
| The event log’s reporter and its Details | On demand, with the shell’s tools once the first tree is usable, or at a page’s first wait or Details before then; requests answered before it loaded are read from Resource Timing | `event-reports`, and the last script of `shell-tools`, in `on_demand_script_bundles` | The comment beside the bundle in `server.py` |
| How every menu closes | On demand, with the shell’s tools once the first tree is usable, or at the first menu opened before then | `menus.js` in `shell-tools`, and the SDK’s `menus.dismissible` in `filter-controls.js`, which forwards to it | The comment beside `menus_url` in `server.py` |
| Remote images and default diff layout preferences | On demand, when the Metabrowser menu opens | `settings-menu` in `on_demand_script_bundles` | The startup script budget surfaced the cost of binding the layout preference on every page |
| The plugin shortcut queue | Eager, since a plugin can attach a key before the registry exists | `queueShortcut` in `plugin-sdk.js` | The comment beside it |
| Line gutter, SDK view helpers, and the syntax service | On demand, beside the view compositor and before any plugin code | `sdk-views` | [exp-037](../../../explorations/performance-loop/experiments/exp-037-startup-imports-and-loading-tiers-for-v012.md) |
| A file’s and a folder’s view header | On demand, beside the view compositor and the SDK view helpers | `view-header` | The comment beside the bundle in `server.py` |
| A page’s file watches on its event stream | On demand, at a view’s first `metabrowser.watchFile` (a table, or a container whose children the tree read); `app.js` keeps only the stream’s connection and forwards `file.changed` | `file-watches` in `on_demand_script_bundles` | The comment beside the bundle in `server.py`; the startup budget had 295 bytes left when it was written (2026-11-20) |
| Pull-request routes and page host | Eager at a `/pull/` address; on demand otherwise | `PULL_PAGE_STARTUP_SCRIPTS`, `pull-route` | exp-037 |
| The watch on a revision’s file ages, and the clause it adds to a filtered count | On demand, the first time a response says the ages are not all in (`dating`, `partial`, `failed`); not offered to a page whose Git cannot read them | `revision-ages` in `on_demand_script_bundles`, when the pin’s Git can date files | The comment beside the bundle in `server.py`: it was a startup script of every pin’s shell, 4,940 bytes (1,896 gzipped) |
| GitPath wire codec | Eager on a pin’s shell, the only page whose addresses spell it; elsewhere it comes with the repository links | `PIN_STARTUP_SCRIPTS`; the first script of `repository-links` | exp-037; the comment beside the bundle in `server.py` |
| What a link in authored text opens | On demand, on a page with a GitHub repository’s identity, beside the text that holds one: a Markdown render, a pull request’s text, a commit’s message, or a rendered diff | `repository-links` in `on_demand_script_bundles`, reached through `metabrowser.loadRepositoryLinks()` | The comment beside the bundle in `server.py` |
| Registering a link for its card, on every page, and loading the card at the first rest ([Tooltips on Links](../../design-system.md#tooltips-on-links)) | On demand, with the SDK view helpers every view already loads; it keeps each registration until a pointer rests on one | `previewLink`, `forgetPreview`, and `disposePreviews` in `plugin-sdk-views.js` (`sdk-views`) | The comment beside them; `server.py`’s `link-previews` bundle has the measurement |
| The link card: the registry of in-app links, the pointer listener, the intent timer, the providers, and the renderer | On demand, at a page’s first pointer rest on a registered link, and never with the resolver, whose wait every surface’s first render shares: measured, a first rest’s card still comes up in every rest’s window, and preloading it in idle time would cost every page with a link its bytes | `link-previews` in `on_demand_script_bundles`: `link-previews.js`, as `window.MetabrowserLinkPreviews`, then `link-preview-providers.js`, which registers with it | The comment beside the bundle in `server.py` |
| Opening a pull request’s, the list’s, or a commit’s page in place from a link | Eager only as `metabrowser.navigation.openRoute`, one line that asks the tab controller; the opener arrives with the shell tools | `openRoute` in `navigation.js` and `main-tabs.js` (`shell-tools`) | The 2026-11-26 note on `startup_script_transfer_kb` in `performance-budgets.toml` |
| The pin guard | Inline on a pin’s shell, before any script can fetch. On demand on the working-tree page of a checkout, with the ref selector that can make its server serve a revision, so a folder’s first paint carries none of it | `_SOURCE_PIN_GUARD_SCRIPT`; `source-ref-selector` in `on_demand_script_bundles` | The comment beside the bundle |
| Chart.js and its plugins | On demand, at the first chart | `chart` | The comment beside it |
| Mermaid, and KPress’s modules that draw its diagrams | On demand, at the first rendered document or `.mmd` file with a diagram; Mermaid then fetches only the chunks of the diagram types drawn | `mermaid`, `kpress-diagrams`, and `kpress-diagram-controls` (module bundles), and `drawDiagrams` in `builtin_plugins/markdown/place-rendered.js` | The comment beside the bundle in `server.py`, and `TOTAL_CAP_BYTES` in `devtools/vendor_assets.py` |
| The changed-files tree every diff and the Pulls tab draw with | On demand: a diff asks beside its comparison, a pull request’s page warms it with the diff plugin on every tab, for its header’s Diff summary and for Changes, and the Pulls tab asks as it mounts | `changed-files-tree`, reached through `metabrowser.loadChangedFilesTree()` | The comment beside the bundle in `server.py` |
| The Diff summary’s tree | On demand, at the summary’s first opening, asked for on the header’s hover or focus | `renderDiffSummary` in `builtin_plugins/diff/diff-view.js` | The comment at the head of `builtin_plugins/diff/diff-summary.js` |
| Inert Markdown render with its table of contents, and the step that places a render | On demand: the first at the first inert render, the second at the first Markdown render | `builtin_plugins/markdown/place-rendered.js` | exp-037 and the comment at its head |
| A refused Markdown render’s source and notice | On demand, at a Markdown view’s first refused render | `builtin_plugins/markdown/rendered.js` | The comment beside the import |
| A pull request’s rendered layer for Markdown, YAML, and JSON | On demand, beside a comparison that names a rendered route; the structured plugin’s tree, through `plugins.load("structured")`, with the first screen’s prefetch and when the first YAML or JSON file is added | `markdownLayer` and `prefetchMarkdown` in `builtin_plugins/diff/index.js`, `ensureStructured` in `builtin_plugins/diff/diff-markdown.js` | The comments beside `markdownLayer` and `ensureStructured` |
| The table view: the table plugin’s module and stylesheet | On demand, at the first file of a kind with a Table view; the delimited plugin starts the load as its own module is evaluated, ahead of the view’s render, since its kind always opens in the Table view | `loadTable` in `builtin_plugins/delimited/index.js`, through `mb.plugins.load("table")` | 23.6 KB, 10.4 KB, and 2.9 KB compressed (gzip -9) for the view, its model, and its stylesheet (2026-11-20), more than a page that shows no table should carry; the comment at the head of `builtin_plugins/delimited/index.js` |
| A store’s views: the fsqlite plugin’s modules and the SQLite plugin’s Info, Table, and Schema views with their models and stylesheet | On demand, at the first fsqlite store selected; each of the store’s views asks for the SQLite plugin’s exports as it mounts, and its Table view at a table’s address the table plugin’s, as the SQLite kind’s does | `mountStoreInfo` in `builtin_plugins/fsqlite/store-view.js` and `mountStoreTable` and `mountStoreSchema` in `builtin_plugins/fsqlite/store-tables.js`, through `mb.plugins.load("sqlite")` | 4.7 KB compressed for the fsqlite plugin’s four modules and 9.7 KB for the SQLite plugin’s six files, its stylesheet included (gzip at level 9, 2026-11-20), drawn only for a store or a database |

Measured on 2026-10-01 as compressed bytes saved, these would move next if the budget
tightens:

| Code | In | Saves | Called by |
| --- | --- | --- | --- |
| KPress document loading and its contents | `plugin-sdk.js` | 2,595 bytes | A Markdown view |
| Rollup fetch and watch | `plugin-sdk.js` | 1,368 bytes | A folder view |
| Plugin data and text fetch helpers | `plugin-sdk.js` | 1,178 bytes | A view |
| The chart helper | `plugin-sdk.js` | 673 bytes | A view that draws a chart |
| File rendering: staging, tabs, print, Load more, the live stream | `app.js` | 7,339 bytes | An opened file |

The first four would join `plugin-sdk-views.js` under its existing guarantee.
The last would sit beside the view compositor, but a page that loads at a file’s address
needs it at once, so it needs its own measurement before it moves.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
