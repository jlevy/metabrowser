# Feature: Folder Views and the Treemap Overview

**Date:** 2026-07-20 (last updated 2026-07-26)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Files already have multiple views with a default: `/api/file` returns a `kind` plus
ordered view descriptors, and the shell renders tabs with lazy mounting and disposal.
Directories sit outside that framework: selecting a folder only expands it, and the
preview shows nothing unless a README was auto-opened.

This plan makes directories first-class in the view framework and adds a default folder
view: a treemap overview of the subtree, in the style of disk-usage inventory tools.
The treemap shows sizes and totals, supports switching the size metric, grouping,
coloring, and gitignored handling, and supports zooming into folders and opening files.
Rollup data reuses the existing bottom-up inventory crawl and streams incrementally, so
complete subtrees render before the root scan finishes and the navigation panel is never
delayed.

The design below is resolved to file and function level.
Two validation tasks remain before the treemap renderer lands: a prior-art brief and a
layout spike that confirms the stated performance budgets.

## Goals

- Generalize the multi-view contract so a directory resolves to a kind with ordered
  views and a default, exactly like files
- Make folder selection preview the folder without breaking expand/collapse in the tree
- Render a treemap overview as the default folder view, driven by inventory rollups
- Provide small joined toggle groups for each axis, combinable independently:
  - Size metric: total bytes (default) or file count
  - Grouping: folder hierarchy (default) or file type by logical extension
  - Color: file type (default) or age; every named cell also carries the tree column’s
    colored age label beside the name
  - Gitignored entries: shown, dimmed (default), or excluded from the visualization and
    its aggregates
- Support hover details, click-to-zoom on folders with navigation sync, click-to-open on
  files, a breadcrumb path, and an up control after zooming
- Reuse the existing walker and `InventoryIndex` aggregates; compute treemap-specific
  rollups (gitignore-excluded totals, extension tallies) at query time from the index
- Deliver rollups incrementally: refresh from the live event channel as directories
  finalize, with explicit pending and truncated states client-side
- Keep first paint, the tree panel, and file previews independent of rollup readiness

## Non-Goals

- Reporting allocated disk blocks; sizes remain logical byte sizes from the inventory
- Persistent indexing or a second filesystem crawl
- Replacing the tree panel or Recent view
- Rendering a treemap cell for every file in very large subtrees; small items aggregate
  into explicit remainder cells
- Archive or container contents (separate roadmap item)
- Editing or file operations from the treemap

## Background

The mechanics this feature needs already exist for files and for aggregates:

- `_classify_with_plugins` and `_views_for_kind` (`server.py`) assemble the kind and
  view-descriptor envelope; `renderFile` (`app.js`) renders the tab bar, mounts the
  default view immediately, lazily mounts other tabs, and disposes plugin views when the
  pane is replaced. Built-in plugins such as markdown declare kinds and views in
  `manifest.toml` and register renderers through `window.metabrowser.registerView`.
- Directories are excluded: `/api/file` returns 404 for them (`_api_file_impl` guards on
  `target.is_file()`), folder rows carry `data-action="toggle"` only, and
  `parseHashRoute` rejects extensionless top-level fragments as in-document anchors.
- The walker (`walk_tree` and `_maybe_finalize` in `walker.py`) finalizes directories
  deepest-first during a breadth-first crawl and records `total_files`, `total_size`,
  and `newest_mtime_ns` per directory; `InventoryIndex` maintains those aggregates
  incrementally on filesystem events (`_update_ancestor_aggregates`) and publishes every
  change as `fs.change` upserts over `/api/events`. Because ancestor aggregates bubble
  to the root on every deep change, the browser’s depth-2 event scope already observes a
  signal for any change anywhere in the tree.
- `_build_inventory_tree` (`tree.py`) demonstrates the bounded read pattern the rollup
  reuses: one O(N) parent-to-children scan of `inventory.entries()` per request, with a
  documented cold-target budget.
- Gitignored entries are indexed and flagged (`FsEntry.gitignored`) but are always
  included in the stored aggregates.
- The design system provides the age ramp tokens (`--file-age-sec` through
  `--file-age-old`), file-type token triplets (`ft-*`), viz surface tokens, and the
  shared tooltip singleton.

## Design

### Resolved Decisions

1. **Directory envelope through `/api/file`.** The existing selection pipeline
   (`selectFile` to `renderFile`) is path-based; one envelope route keeps hash routing,
   caching, and error handling uniform.
   No parallel folder route.
2. **Core assigns the `folder` kind; plugins contribute the views.** Directory
   classification cannot be expressed in manifest match rules, so it lives in the
   `api_file` handler, exactly as the imperative fallback chain owns `text` and
   `binary`. The built-in `folder` plugin declares only `[[view]]` blocks, like the text
   and binary manifests.
3. **Folder view lists are content-aware.** The Treemap view is always present.
   The server includes the README view only when the folder has a direct-child README,
   so a README-less folder renders the Treemap without a redundant one-item tab bar.
   Other plugin-provided folder views remain unaffected.
4. **The root folder is the homepage.** With no explicit hash route, the shell selects
   the root folder and its default treemap view.
   A direct-child README remains available through the folder’s README tab and never
   replaces the folder view.
   Explicit file and folder deep links, including CLI `--path`, still select their
   requested target.
5. **Rollups are computed at query time from the index, not stored.** A single
   parent-to-children scan per request follows the `_build_inventory_tree` precedent.
   Stored per-directory aggregates stay exactly as they are.
   If measurement exceeds the stated budget, the escape hatch is a generation-keyed
   cache of the adjacency map, not walker changes.
6. **Treemap rendering is hand-rolled squarified layout in plain DOM.** No new
   dependency: the squarify algorithm is ~150 lines, cells are positioned `div`s with
   real selectable text labels, and culling bounds DOM size.
   Canvas conflicts with the design-system rules on selectable text; a vendored layout
   library is not worth a supply-chain review for one algorithm.
7. **Zoom is navigation.** Clicking a directory cell opens that folder through the
   normal selection pipeline (hash, tree selection, new envelope, treemap remount at the
   new root). The treemap holds no private location state; it may retain only a
   short-lived transition direction and destination so the old and new roots read as one
   spatial zoom. Reduced-motion users navigate immediately.
   Breadcrumb and up controls remain shell chrome shared by every folder view, while the
   treemap also exposes an explicit Zoom out control beside its visualization settings.
8. **Live refresh rides the existing event stream.** The shell re-dispatches store
   changes as a DOM `CustomEvent`; the SDK wraps fetch-plus-refresh in a `watchRollup`
   helper with trailing debounce.
   No new SSE scope in this plan.
9. **Toggle state persists through the SDK preference service** (`mb.prefs`, one
   versioned key over host-only cookies so the choice survives across per-root ports);
   toggles never appear in the hash.

### Server: Folder Envelope (`server.py`, `file_kinds.py`)

- `_api_file_impl` (server.py): split the current
  `if target is None or not target.is_file()` guard.
  `target is None` stays 404; a new `target.is_dir()` branch returns
  `await _api_folder_envelope(subpath, target)`; remaining non-files stay 404.
- New `_api_folder_envelope(subpath: str, target: Path) -> JSONResponse`:
  - reads `inventory.get(subpath)` for aggregates (entry may be absent early in a scan);
  - finds a direct-child README via the bounded `_find_dir_readme(target)` helper in a
    thread;
  - returns
    `{type: "folder", kind: "folder", path, name, views, dir: {total_files, total_size, mtime, gitignored, state}, readme_path}`
    where `state` is `"pending"` when aggregates are null and `mtime` follows the tree
    contract (null pending, `0.0` empty, else seconds);
  - derives `views` from `_views_for_kind("folder")` and omits the built-in `readme`
    descriptor when `readme_path` is empty;
  - sets `cache-control: no-store` (the envelope is tiny and aggregates change during
    scans; the client also skips its `fileCache` for folder envelopes).
- `VIEW_REGISTRY` (file_kinds.py): add `"folder": []` documenting the core-owned kind;
  the merged views arrive from the plugin manifest through `_PLUGIN_VIEWS_BY_KIND`.
- `_views_for_kind` needs no change; the merge and forced-default rules are generic.

### Server: Rollup Query and Route (`inventory.py`, `server.py`, `wire_models.py`, `settings.py`)

- New `InventoryIndex.rollup(path, *, depth, top, ext_top) -> dict | None`
  (inventory.py). Returns `None` when the index has no entry for `path`. One pass over
  `self._entries` builds `children_by_parent`; a recursive helper then computes, per
  directory, full-subtree totals regardless of `depth`:
  - `total_files` / `total_size` (all entries) and `unignored_files` / `unignored_size`
    (skipping entries whose own or inherited `gitignored` flag is set, propagated down
    the recursion like `parent_ignored` in `_build_inventory_subtree`);
  - `mtime` (newest descendant, seconds, tree contract) and `state` (`"pending"` when
    the stored `total_files` is `None`, else `"complete"`);
  - `dominant_ext`: the extension with the largest byte share in the subtree;
  - children: dirs and files mixed, sorted by `total_size`/`size` descending; the first
    `top` emit as nodes (files as `{name, path, type, size, mtime, ext, gitignored}`),
    the remainder collapses into
    `rest: {dirs, files, size, unignored_size, unignored_files}`;
  - below `depth`, a directory node emits `children: null` (the tree’s lazy sentinel)
    while its totals remain full-subtree.
  - The envelope also carries `ext_tallies` for the requested root only: the top
    `ext_top` extensions by bytes as `[ext, files, size]` rows plus one remainder row.
- New route `api_rollup` (server.py) at `GET /api/rollup?path=&depth=&top=&ext_top=`:
  `_safe_path` plus `is_dir` guard exactly like `api_tree`; the same inventory
  start/cold-start-wait block as `api_tree`, factored into a shared helper
  `_ensure_inventory_serving(subpath)` used by both routes; clamped params; response
  `{root, path, node, ext_tallies, index_status, indexed_files, max_files, truncated}`.
  No ETag in v1; bodies ride the existing gzip middleware.
- `settings.py`: `ROLLUP_DEFAULT_DEPTH = 3`, `ROLLUP_MAX_DEPTH = 6`,
  `ROLLUP_DEFAULT_TOP = 40`, `ROLLUP_MAX_TOP = 200`, `ROLLUP_DEFAULT_EXT_TOP = 12`,
  `ROLLUP_MAX_EXT_TOP = 32`, exposed to the browser through `client_settings_dict`.
- `wire_models.py`: `RollupDirNode`, `RollupFileNode`, `RollupRest` TypedDicts and a
  recursive `validate_rollup_node`, following the `validate_tree_node` pattern, used by
  the route tests.
- Bounds: `top` caps one directory and `ROLLUP_MAX_NODES` (1,200) caps the whole
  response — a balanced tree multiplies per level, so only the global budget bounds
  payloads. Enforced by tests: an adversarial 40×40×40 tree (64k files) emits exactly the
  cap (~160 KiB pre-gzip, asserted <400 KiB) with rest buckets and `children: null`
  sentinels marking every cut; query CPU is printed by the same tests (~250 ms at 65k
  entries for the full-index adversarial case, single-digit ms on ordinary
  repositories). A generation-keyed adjacency cache remains decision 5’s escape hatch if
  scoped-request CPU becomes the bottleneck.

### Browser Shell (`app.js`, `styles.css`)

- `renderTreeNodes` folder branch: wrap the chevron in
  `<span class="tree-toggle" data-role="toggle">` and change the row’s `data-action` to
  `"select-dir"`. The chevron keeps a distinct hover affordance (new `.tree-toggle`
  rules in styles.css).
- Tree click handler: a `target.closest('[data-role="toggle"]')` hit runs the existing
  toggle logic (including shift-recursive expand); otherwise `"select-dir"` runs
  `setSelectedPath(path)` plus `selectFile(path)` and expands (never collapses) the row,
  reusing the lazy-subtree load.
- `parseHashRoute`: capture whether the decoded fragment ends with `/` before stripping.
  A trailing slash marks a directory path: skip the in-document-anchor heuristic and
  return the stripped path (the fragment `#/` means the served root).
  `selectFile` writes folder hashes with the trailing-slash marker once the envelope
  identifies a folder.
- `revealInTree`: final row lookup generalizes from `.tree-file[data-path=…]` to
  `.tree-item[data-path=…]` so directory rows resolve; `navigateToPath` then works for
  directories unchanged.
- `selectFile`: on a `kind: "folder"` response, skip `fileCache` insertion, revalidation
  bookkeeping, and `maybeOpenLiveStream`; everything else (abort handling, spinner,
  `renderFile`) is shared.
- `renderFile`: when `data.kind === "folder"`, the header is built by a new
  `renderFolderHeader(data)`: breadcrumb segments (root plus each ancestor, each
  navigating to that directory), an up button (disabled at the root), and the aggregate
  summary (`sizeHtml`, count, age).
  Tabs, lazy mounting, and disposal flow through the existing code path; a single view
  renders without a tab bar, and `ctx.raw` is the folder envelope.
- `init()`: when there is no hash, call `selectFile("")` immediately so the root folder
  request runs in parallel with the tree load and lands on the default treemap.
  The server and shell do not seed a root README as the initial file.
- The store notifier (`notifyFileStoreSubscribers`) additionally dispatches `window`
  CustomEvent `metabrowser:inventory-change` with the changed paths, the signal
  `watchRollup` listens for.

### Plugin SDK (`plugin_sdk.js`)

- `fetchRollup(path, opts)`: GET `/api/rollup` with abort support, defaults from
  `window.METABROWSER_SETTINGS`.
- `watchRollup(path, opts, onUpdate)`: initial fetch plus refresh on
  `metabrowser:inventory-change` events whose paths are ancestors of, equal to, or under
  `path` (ancestor bubbling makes this sufficient for deep changes), with a trailing
  debounce (default 1000 ms).
  Returns `{refresh, dispose}`; `dispose` detaches the listener and aborts in-flight
  fetches.
- `ageBucket(mtimeSeconds)`: returns `"sec" | "min" | "hr" | "day" | "wk" | "old"` or
  null, sharing the thresholds `formatAge` uses (app.js refactors to call it so the ramp
  cannot drift).
- `tooltip` and `fileTypeClass(path)`: thin proxies over the shell’s
  `MetabrowserTooltip` and `MetabrowserFileTypes.classFor`, following the existing
  `icons` proxy pattern, so the plugin never touches app.js globals.

### Built-in Folder Plugin (`src/metabrowser/builtin_plugins/folder/`)

- `manifest.toml`: `[plugin] name = "folder"`, `extra_scripts = ["treemap_layout.js"]`;
  two `[[view]]` blocks for kind `folder`: `treemap` ("Treemap", `default = true`) and
  `readme` ("README", `render_runtime = "kpress"`, printable,
  `print_profile = "document"`). No `[[kind]]` rules (decision 2).
- `treemap_layout.js` (classic script, global `MetabrowserTreemapLayout`, strict
  check-JS): pure geometry, no DOM. `squarify(items, rect)` implements the Bruls,
  Huizing, and van Wijk algorithm; `layoutTree(rollupNode, viewport, opts)` walks the
  rollup, applies the active metric and grouping, and returns positioned cells with one
  bounded preview layer inside sufficiently large directory cells, culling cells below
  `opts.minCellPx`, capping total cells at `opts.maxCells` (default 800), and
  synthesizing remainder cells from `rest` buckets and culled children.
  Grouping `"type"` lays out the envelope `ext_tallies` instead of the directory
  hierarchy, one cell per extension.
- `index.js` registers both views:
  - `readme`: renders through the exported markdown built-ins (`mb.builtins.markdown`)
    against a context whose `path` is `raw.readme_path`. The folder envelope advertises
    this view only when the path exists; the renderer retains a defensive empty state
    for direct SDK invocation.
  - `treemap`: mounts a toolbar (three joined toggle groups plus the three-state
    gitignored control), the cell viewport, and a compact legend; holds
    `{metric, grouping, color, ignored}` persisted under the
    `metabrowser.folder.treemap` preference key; starts `mb.watchRollup(ctx.path, …)`
    and relayouts on data or toggle changes (toggle changes never refetch — both
    aggregate variants and `dominant_ext` are already in the payload); registers a
    `dispose` that tears down the watch handle.
  - Cells and zoom: directory cells use a zoom-in cursor and accessible zoom language,
    play a short exit transition, then navigate via `mb.openPath` (decision 7); the
    replacement treemap plays the matching entrance transition once its rollup is ready.
    A visible Zoom out button performs the inverse transition and navigates to the
    structural parent. File cells open without a spatial zoom.
    Reduced-motion mode skips both transition delays.
    Hover uses `mb.tooltip` with path, size, file count, age, and the directory action;
    keyboard support is roving tabindex with arrow-key movement in layout order, Enter
    to activate, and Backspace for the parent directory.
  - Nested preview: hierarchy grouping draws at most one child layer inside each
    sufficiently large directory cell.
    The parent header and inner boundary remain visually distinct, and nested
    directories remain independently zoomable.
    Smaller descendants continue to aggregate instead of producing illegible targets.
  - Color: `type` (default) applies the `ft-*` class (files) or `dominant_ext` class
    (directories); `age` maps `mb.ageBucket` to the new fill tokens; independent of the
    fill, `mb.ageLabelHtml` puts the header’s colored age chip beside each dir and file
    name; the `dimmed` ignored state applies a muted opacity class, `hidden` relayouts
    from the unignored aggregates.
  - Pending directories render skeleton cells (tally-pending pattern); a truncated index
    renders a persistent notice sourced from the envelope fields.
- `styles.css` (plugin-owned): consumes host tokens plus the new age fill tokens; no
  literal colors, mirroring the structured plugin’s stylesheet contract.
- Core `styles.css` additions: `--file-age-fill-sec` … `--file-age-fill-old` with
  dark-theme overrides (the existing age tokens are text colors and too saturated for
  large fills), `.tree-toggle` hover, and folder-header/breadcrumb rules.

### Navigation Equivalence

The navigation pane and the folder overviews are two faces of one traversal; clicking
around either must reach everything and keep the other in sync.
Invariants:

1. **Same reachability.** Any folder or file reachable from tree rows is reachable from
   overview clicks (directory cells, breadcrumb segments, the up control) and vice
   versa; overview navigation works even for rows the tree has not materialized
   (`navigateToPath` opens the preview when `revealInTree` cannot resolve a row).
2. **One current location.** The tree selection, the overview’s root, and the URL hash
   always agree; every navigation path funnels through `navigateToPath`.
3. **Symmetric side effects.** A tree folder click previews without collapsing; an
   overview click reveals and expands the tree along the path.
4. **History walks folders.** Folder-to-folder navigation pushes history entries so the
   browser back button retraces zooms (the up button remains the structural ancestor
   move); file selection keeps today’s lateral `replaceState`.
5. **Same filters.** Whatever filtering is active applies identically to both surfaces
   (the unified-filtering plan owns the mechanism).

Invariants 1–3 hold in the current implementation; 4 is open work tracked in this plan’s
remaining phase, and 5 lands with the unified-filtering plan.

## Implementation Plan

### Phase 1: Folder Views Framework

Shippable on its own: folder selection, breadcrumb, and the conditional README view.

- [x] Folder envelope: `_api_folder_envelope`, `_find_dir_readme`,
  `VIEW_REGISTRY["folder"]`, no-store headers, tests
  (`tests/test_api_folder_envelope.py`)
- [x] Shell wiring: tree-row toggle/select split, click handler branch, directory hash
  marker in `parseHashRoute` and `selectFile`, `revealInTree` generalization,
  `renderFolderHeader` with breadcrumb and up, root-folder landing in `init()`,
  `.tree-toggle` and header styles, DOM tests under `tests/dom/`
- [x] Built-in `folder` plugin with manifest and the conditionally exposed README view
  (markdown built-ins reuse, defensive empty state), Node `vm` registration tests
  (`tests/test_folder_plugin_behavior_js.py`)

### Phase 2: Rollup Data Plane

Independent of Phase 1; Phase 3 needs both.

- [x] `InventoryIndex.rollup` with deterministic fixtures (partial, truncated,
  gitignored, symlinked, moved, deleted), budget measurement on a synthetic 100k-entry
  index (`tests/test_browser_rollup.py`)
- [x] `api_rollup` route, `_ensure_inventory_serving` refactor shared with `api_tree`,
  settings constants and client exposure, `wire_models` rollup validators, route tests
  (`tests/test_rollup_route.py`, `tests/test_browser_wire_shape.py`)
- [x] SDK surface: `fetchRollup`, `watchRollup` (debounce, ancestor filtering, dispose),
  `ageBucket` with the `formatAge` refactor, `tooltip` and `fileTypeClass` proxies, the
  `metabrowser:inventory-change` shell event, SDK `vm` tests

### Phase 3: Treemap View

- [x] Prior-art brief and layout spike: survey the disk-usage tools named in Background
  for layout, small-file aggregation, and zoom conventions; spike `squarify` on fixture
  data against the layout budget (≤16 ms for 800 cells); record both in
  `docs/project/research/` and fold corrections into this spec
- [x] `treemap_layout.js`: squarify, `layoutTree`, culling, remainder synthesis,
  type-grouping mode, golden `vm` tests (`tests/test_folder_treemap_layout_js.py`)
- [x] Treemap renderer in `index.js`: toolbar toggles with persistence, cell rendering
  with age and type color modes, gitignored three-state, hover tooltip, click
  navigation, keyboard model, pending and truncated presentations, plugin styles, core
  fill tokens
- [x] Live refresh: `watchRollup` wiring end to end (filesystem change to ancestor
  upsert to debounced refetch to relayout), plus an integration test from a real
  filesystem mutation (`test_rollup_reflects_real_fs_mutation_through_fs_change`)
- [x] History semantics for navigation equivalence: folder-to-folder navigation uses
  `history.pushState` so browser back retraces zooms; file selection keeps
  `replaceState`; `popstate` routes through `navigateToPath`; DOM tests for the
  back-button trail
- [x] Validation: budgets on a synthetic large root, the design-system review checklist
  in both themes (contrast audit darkened the `--file-age-*` text ramp for AA and added
  its dark variants; two-tone treemap focus ring; print and reduced-motion verified),
  docs updates (`docs/plugins.md` folder kind, `docs/design-system.md` fill tokens,
  `docs/architecture.md` folder envelope note)
- [x] Spatial zoom refinement: directional enter/exit transitions around route
  navigation, an explicit Zoom out control, clearer one-level nested previews, and
  reduced-motion behavior (`mb-xojs`)

## Testing Strategy

- Python unit and contract tests as listed per phase; every new wire shape passes its
  `wire_models` validator in tests
- Node `vm` tests for plugin registration, layout geometry (areas sum to the rect,
  aspect-ratio quality, culling, remainder cells), and SDK debounce behavior
- DOM tests for the toggle/select split, hash round-tripping, breadcrumb navigation, and
  treemap toggle state
- Renderer behavior tests for zoom-in and zoom-out destinations, directional transition
  classes, reduced-motion timing, and bounded nested-preview markup
- One end-to-end test from filesystem mutation through `fs.change` to a treemap refresh
- Budget measurements recorded in test output on public synthetic fixtures: rollup CPU
  and payload, layout time, render-to-paint on 800 cells

## Rollout Plan

Land phases in order; each is releasable.
Phase 1 changes folder clicks from toggle-only to select-plus-expand and adds the
conditional README view; the treemap appears in Phase 3 as the default folder view.
The root folder opens on the Treemap whether or not it has a README (decision 4). The
nav panel, Recent view, and file previews keep their current behavior and timing; rollup
work stays off the request path for unrelated views.

## Open Questions

- Should treemap toggle preferences move from `localStorage` to the host-only cookie
  pattern the theme uses, so they follow the user across per-folder server ports?
- Is `dominant_ext` coloring readable enough for directory cells in type mode, or should
  directories stay neutral there?
  (Settle during the layout spike.)
- Does the rollup budget hold at the 500k-entry index cap, or does the generation-keyed
  adjacency cache (decision 5) become necessary?

## References

- [Core architecture](../../../architecture.md)
- [Design system](../../../design-system.md)
- [Plugin authoring](../../../plugins.md)
- [Scanning state and recent directories](plan-2026-07-16-scanning-state-and-recent-directories.md)
- [Scalable file search](plan-2026-07-17-scalable-file-search.md)
- [Web diff viewer research brief](../../research/research-2026-07-17-web-diff-viewer-architecture.md)
  (research-brief format precedent)
- Related beads: mb-7uta (SDK streaming), mb-t1wt (plugin event subscription;
  `watchRollup` is a scoped step toward it), mb-uh6p (non-file plugin surfaces), mb-7l9k
  (large-directory budgets), mb-0b2h (shell modularization)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
