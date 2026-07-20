# Feature: Folder Views and the Treemap Overview

**Date:** 2026-07-20 (last updated 2026-07-20)

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

Implementation starts with a background research phase whose findings are recorded in a
research brief and folded back into this spec before the build phases begin.

## Goals

- Generalize the multi-view contract so a directory resolves to a kind with ordered
  views and a default, exactly like files
- Make folder selection preview the folder without breaking expand/collapse in the tree
- Render a treemap overview as the default folder view, driven by inventory rollups
- Provide small joined toggle groups for each axis, combinable independently:
  - Size metric: total bytes (default) or file count
  - Grouping: folder hierarchy (default) or file type by logical extension
  - Color: age (default, same semantics and tokens as the tree column) or file type
  - Gitignored entries: shown, dimmed (default), or excluded from the visualization and
    its aggregates
- Support hover details, click-to-zoom on folders with navigation sync, click-to-open on
  files, a breadcrumb path, and an up control after zooming
- Reuse the existing walker and `InventoryIndex` aggregates; extend them only where the
  treemap needs more (per-extension tallies, gitignore-excluded totals)
- Deliver rollups incrementally bottom-up: each directory becomes renderable when its
  scan completes, stitched client-side with explicit pending and truncated states
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
- Directories are excluded: `/api/file` returns 404 for them, folder rows only toggle,
  and hash routing rejects directory paths.
- The walker (`walk_tree` and `_maybe_finalize` in `walker.py`) already finalizes
  directories deepest-first during a breadth-first crawl and records `total_files`,
  `total_size`, and `newest_mtime_ns` per directory; `InventoryIndex` maintains those
  aggregates incrementally on filesystem events and publishes them as `fs.change`
  upserts over `/api/events`. A pending directory is explicit (`total_files` is null),
  which the tree already renders as a skeleton tally.
- Gitignored entries are indexed and flagged (`FsEntry.gitignored`) but are always
  included in aggregates today.
- The design system provides the age ramp tokens (`--file-age-sec` through
  `--file-age-old`), file-type token triplets (`ft-*`), viz surface tokens, and a shared
  tooltip.

What is missing: a directory kind and envelope, folder selection and routing, treemap
rendering, per-extension rollups, gitignore-excluded totals, and a bounded way to fetch
deep subtree rollups (the live event scope covers only depth 2).

Disk-usage visualizers (WinDirStat, SequoiaView, GrandPerspective, DaisyDisk, Baobab,
SpaceSniffer, TreeSize, WizTree, and terminal tools such as ncdu, dust, dua, and gdu)
have converged on patterns for layout, small-file aggregation, and zoom that the
research phase surveys before we commit to a design.

## Design

The sections below record the intended shape; items marked *research-gated* are
confirmed or revised by Phase 1 findings.

### Approach

Three parts, layered:

1. **Folder views framework (core).** Directories resolve to a `folder` kind through the
   same classification and view-merge path as files, so built-in and installed plugins
   can contribute folder views and exactly one default applies.
   Folder rows separate the expand/collapse affordance from selection, selection routes
   the directory path through the hash and preview pipeline, and the folder view header
   carries a breadcrumb with an up control.
2. **Rollup data (core).** The inventory answers bounded subtree rollup queries and
   keeps streaming per-directory finalization through the existing event channel.
   The walker and inventory gain per-extension tallies and gitignore-excluded totals
   alongside the current aggregates (*research-gated:* precomputed and maintained versus
   computed per query behind a generation-keyed cache).
3. **Treemap view (built-in plugin).** The treemap renderer, its toggles, and its styles
   ship as a built-in plugin like markdown, using only the documented SDK plus the
   rollup endpoint. The layout algorithm and rendering technology are *research-gated*
   with a strong prior toward squarified layout in plain DOM with culling, given the
   design-system rules on selectable text and canvas.

### Components

- Core server: directory classification into the view envelope (`_views_for_kind`
  merge), a bounded rollup query on `InventoryIndex`, dual all/visible accumulators and
  per-extension tallies in `walker.py` and `inventory.py`, wire models and validation
- Core browser shell: folder selection and hash routes for directories, breadcrumb and
  up control, dispatch of folder envelopes through `renderFile`
- Built-in `folder_treemap` plugin: manifest declaring the `folder` kind views (treemap
  overview default; README tab when the folder has a direct-child README, reusing the
  markdown built-ins), renderer, toggle controls, plugin styles on design tokens
- Client rollup store: per-scope subtree store fed by an initial fetch plus `fs.change`
  upserts, with explicit pending, complete, and truncated node states the renderer maps
  to skeleton, live, and truncation presentations

### API Changes

Provisional contract, finalized by research task R3:

- `/api/file` (or a parallel folder route) returns a directory envelope:
  `kind: "folder"` and merged view descriptors, instead of 404

- A bounded rollup endpoint with semantics equivalent to:

  ```text
  GET /api/rollup?path=src&depth=3&top=40
  ```

  returning, per directory node: totals and visible-only totals for bytes and file
  counts, `newest_mtime_ns`, a bounded per-extension tally, the top children by the
  requested metric with an explicit remainder bucket, scan state (pending, complete, or
  truncated), and the inventory generation

- Live updates reuse `fs.change` upserts for finalized directories; clients stitch them
  into the rollup store and refetch on generation gaps, matching the resync behavior in
  the scanning-state plan

Payloads stay bounded regardless of subtree size, remain compressed by the existing gzip
middleware, and never present capped or pending totals as exhaustive.

### Interactions

- Hover highlights a cell and shows the shared tooltip: path, size, file count, age
- Clicking a directory cell zooms the treemap to that directory, updates the hash, and
  syncs the tree selection; clicking a file cell opens the file through the normal file
  preview
- A breadcrumb shows the zoom path; an up control returns toward the served root
- Toggle changes relayout the current data without refetching when the loaded rollup
  already covers the selection
- Keyboard access and non-color cues follow the design-system accessibility checklist
  (*research-gated:* the keyboard navigation model for treemap cells)

## Implementation Plan

### Phase 1: Background Research

Deliverable: a research brief in `docs/project/research/` recording decisions, budgets,
and rejected alternatives, plus updates to the research-gated items in this spec.

- [ ] R1 Prior art: survey how WinDirStat, SequoiaView, GrandPerspective, DaisyDisk,
  Baobab, SpaceSniffer, TreeSize, WizTree, ncdu, dust, dua, and gdu handle
  scan-while-render, layout choice, small-file aggregation, remainder and free-space
  cells, color mapping, and zoom controls
- [ ] R2 Layout and rendering: compare slice-and-dice, squarified, strip, and
  order-preserving layouts for readability and stability under live updates; compare
  DOM, SVG, and canvas against the design-system constraints (selectable text, tokens,
  reduced motion, accessibility); define culling and label thresholds; decide
  hand-rolled squarify versus a vendored layout library under the supply-chain policy
  and vendor size caps; measure layout and paint on a synthetic large-tree fixture
- [ ] R3 Rollups and transport: decide the per-extension tally representation and its
  memory bound; decide precomputed versus query-time visible-only totals; choose the
  rollup payload shape (nesting, top-N, remainder buckets) and confirm reuse of
  `fs.change` for stitching; measure rollup query cost, payload sizes, and update churn
  at the inventory cap
- [ ] R4 Folder-kind framework: choose the directory envelope route; define folder
  selection versus expand/collapse in the tree and hash semantics for directories;
  define the default-view policy where a README exists; define the treemap keyboard
  model; confirm the core-versus-plugin split of endpoint, store, and renderer

### Phase 2: Folder Views Framework

- [ ] Classify directories into the view envelope with merged plugin views and one
  default; keep 404 semantics for paths outside the root
- [ ] Wire folder selection, directory hash routes, breadcrumb, and up control without
  changing expand/collapse behavior
- [ ] Add the README folder view backed by the markdown built-ins
- [ ] Test envelope contracts, routing, lazy mount and disposal for folder views, and
  independence of tree rendering from folder-view readiness

### Phase 3: Treemap Data and View

- [ ] Add dual accumulators and per-extension tallies to the walker and inventory with
  deterministic partial, truncated, ignored, and symlinked fixtures
- [ ] Add the bounded rollup endpoint with validation, generation metadata, and wire
  tests
- [ ] Build the treemap renderer with the four toggle groups, hover, zoom, open-file,
  pending and truncated presentations, and plugin styles on design tokens
- [ ] Stitch live `fs.change` updates into the rollup store with debounced relayout and
  resync on generation gaps
- [ ] Validate performance budgets on synthetic large roots and run the design-system
  review checklist in both themes

## Testing Strategy

- Unit-test accumulator math (including gitignore-excluded totals and extension tallies)
  across partial, truncated, moved, and deleted subtrees
- Contract-test rollup payload bounds, node states, and generation behavior
- Node `vm` tests for plugin registration; DOM tests for toggle state, zoom, and
  navigation sync; end-to-end coverage from filesystem change to treemap update
- Measure crawl overhead added by new accumulators, rollup latency, payload size, and
  relayout cost on public synthetic large-tree fixtures

## Rollout Plan

Complete Phase 1 and update this spec before building.
Ship the framework with the README folder view first so folder selection is immediately
useful, then enable the treemap plugin as the default folder view.
The nav panel, Recent view, and file previews keep their current behavior and timing
throughout; rollup work stays off the request path for unrelated views.

## Open Questions

- Default-view policy when a folder has a README: does the treemap remain the default
  everywhere, or does a README-bearing folder (including the served root at startup)
  default to the README tab?
- Is the three-state gitignored control (shown, dimmed, hidden) one joined toggle, or a
  checkbox plus a dim option?
- How should symlinks and hard links count toward totals (the walker currently does not
  follow symlinks)?
- Do extension tallies stay bounded per directory (top-K plus remainder), and what K
  keeps type grouping honest on messy trees?
- Should zoom state live in the hash beyond the directory path (for example the active
  toggles), or reset per navigation?
- Do the age ramp tokens need a dark-theme override before the treemap uses them as
  large fills rather than text color?

## References

- [Core architecture](../../../architecture.md)
- [Design system](../../../design-system.md)
- [Plugin authoring](../../../plugins.md)
- [Scanning state and recent directories](plan-2026-07-16-scanning-state-and-recent-directories.md)
- [Scalable file search](plan-2026-07-17-scalable-file-search.md)
- [Web diff viewer research brief](../../research/research-2026-07-17-web-diff-viewer-architecture.md)
  (research-brief format precedent)
- Related beads: mb-7uta (SDK streaming), mb-uh6p (non-file plugin surfaces), mb-7l9k
  (large-directory budgets), mb-0b2h (shell modularization), mb-725d (vendored ESM
  bundling)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
