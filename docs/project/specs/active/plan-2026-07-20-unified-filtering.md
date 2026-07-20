# Feature: Unified Filtering Across Navigation and Folder Views

**Date:** 2026-07-20 (last updated 2026-07-20)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser filters files in several unrelated ways today: the Recent tab is an age
filter wearing a tab, the treemap has its own three-state gitignored control, the
planned search feature defines keyword, extension, and age predicates, and the tree dims
gitignored rows unconditionally.
Each surface invents its own controls.

This plan defines one filtering vocabulary — a small set of dimensions, two application
modes, and named presets — owned by one shared state object.
The navigation pane shows the simplified form (two preset chips plus one menu); folder
views such as the treemap show the full form; both read and write the same state.
The Recent tab becomes the Recent preset of that vocabulary rather than a separate
place, and eventually retires.

## Goals

- Define the filter dimensions once, orthogonally to any surface:
  - **Activity**: live files (the active tracker’s `FsEntry.active` flag)
  - **Age**: modification-time window (the existing `1h / 24h / 7d / 30d` set)
  - **Type**: file-type families (the `ft-*` subtype vocabulary, expandable to exact
    logical extensions)
  - **Visibility**: gitignored entries (shown, dimmed, hidden)
- Support two application modes everywhere: **dim** (non-matching entries stay in place
  but fade, preserving context) and **hide** (non-matching entries leave, and aggregates
  recompute)
- Ship two preset chips — **Current** (activity: live) and **Recent** (age within a
  default window) — with every other control behind one compact filter menu
- Keep one `FilterState` in the shell, exposed through the SDK, so the navigation bar,
  the treemap, and future plugin views bind to the same state with the same chip and
  menu components
- Treat the search spec’s keyword predicate as the one typed dimension of the same
  vocabulary, and reuse its endpoint as the hide-mode tree provider
- Keep dim mode purely client-side from data already in the store (`mtime_ns`, `ext`,
  `gitignored`, `active` are all on every entry), so filtering never blocks the tree
- Fold the Recent tab into the Recent preset without losing what makes it good: the
  recency-clustered presentation, counts, and live updates

## Non-Goals

- Content search (the search spec owns keyword-over-paths; content search is separate)
- New crawls, index changes, or per-filter server endpoints (existing endpoints gain
  parameters; `/api/recent` already accepts extension and prefix filters)
- Saved or user-named filter combinations (presets are fixed in the first version)
- Removing the Recent tab before the parity checklist in Phase 3 passes
- Filtering inside non-listing views (a README or document view ignores filters)

## Background

What exists, and what each piece contributes to the unified model:

- The Recent tab (`api_recent`, `collect_recent_entries` in `recent.py`) is an age
  filter plus a recency-clustered presentation; it already exposes window chips
  (`RECENT_WINDOWS`) and accepts `ext_filter` / `prefix_filter` server-side.
  Its wire result reports totals and truncation honestly.
- The treemap’s gitignored control (shown / dimmed / hidden) is the two application
  modes plus off — evidence the mode model covers real cases.
  Its `hidden` state relayouts from the `unignored_*` aggregate variants that
  `InventoryIndex.rollup` computes per request: the pattern that generalizes to
  arbitrary filtered aggregates.
- The scalable-search plan defines keyword, logical-extension, and recency predicates
  combined with AND, served by a bounded `/api/search` that returns matches plus the
  ancestors needed to draw a tree — exactly a hide-mode tree provider.
- The active tracker flips `FsEntry.active` through the same event plane the store
  already consumes, so a Current filter updates live without new transport.
- Every store entry and tree row already carries `mtime_ns`, `ext`, `gitignored`, and
  `active`, so dim mode needs no server support at all.

## Design

### The Vocabulary

Three orthogonal parts, fixed across surfaces:

1. **Dimensions** (what qualifies): activity, age, type, visibility, plus the typed
   keyword dimension from the search spec.
   Dimensions combine with AND; values within a dimension combine with OR.
2. **Mode** (what happens to non-matching entries): `dim` keeps them in place with the
   muted treatment the tree already uses for gitignored rows; `hide` removes them and
   recomputes aggregates.
   Visibility keeps its own three-state (its `dimmed` / `hidden` are the same two modes
   applied to one dimension).
3. **Presets** (fast paths): a preset chip is a named value assignment, not a separate
   mechanism. **Current** sets activity=live; **Recent** sets age=24h (window adjustable
   in the menu). Toggling a chip on or off writes through to the same state the menu
   edits.

Presentation stays per-surface and orthogonal: the tree shows dimmed or pruned rows, the
Recent preset keeps its recency-clustered list presentation on the nav, and the treemap
dims cells or relayouts.

### FilterState (core shell)

- New strict module `static/filter_state.js` exposing `window.MetabrowserFilterState`:
  `get()`, `set(patch)`, `subscribe(listener)`, `clear()`, and the preset definitions.
  State shape:
  `{current: bool, ageWindow: "1h"|"24h"|"7d"|"30d"|null, types: string[]|null, ignored: "shown"|"dimmed"|"hidden", mode: "dim"|"hide"}`.
- Persisted under one localStorage key (`metabrowser.filters`); every change dispatches
  a `metabrowser:filter-change` CustomEvent (the `watchRollup` pattern).
- SDK proxy `mb.filters` (get / set / subscribe) so plugin views never touch the global
  directly. The treemap’s ignored control migrates from its private localStorage state to
  this shared dimension.
- A shared chip-row and menu primitive (core styles, reused classes) renders the same
  controls at both densities, so the vocabulary looks identical everywhere.

### Navigation Pane (simplified form)

- A compact filter bar above the tree, outside the replaceable tree container (the
  search spec’s placement rule): `[Current] [Recent] [⏷ filter menu]`, with an active
  count badge on the menu button and a clear affordance when any filter is set.
- The menu holds the full set: age window chips (reusing `RECENT_WINDOWS`), type family
  multi-select, the visibility three-state, the dim/hide mode switch, and Clear.
- Dim mode (default): non-matching rows get the muted treatment client-side; matching
  rows keep their age and size coloring.
  No server round trip.
- Hide mode: the tree renders from `/api/search` with an empty keyword and the active
  ext/age predicates (matches plus ancestors, incompleteness reported) — this phase
  depends on the scalable-search plan’s endpoint and falls back to dim until it lands.
- Recent preset on the nav activates the existing recency-clustered presentation, scoped
  by whatever other filters are active; Current shows live files with the existing
  activity indicators.
- The Recent tab stays during the transition and retires in Phase 3; the nav header then
  has a single Files pane with the filter bar.

### Folder Views and the Treemap (full form)

- The treemap toolbar separates **encodings** (Metric, Grouping, Color — view-local,
  unchanged) from **filters** (shared state via `mb.filters`).
- Dim mode adds the muted cell class to non-matching cells (per-cell `ext` and `mtime`
  are already in the rollup payload; directory cells dim only when their newest mtime or
  dominant type rules them out entirely).
- Hide mode extends `/api/rollup` with `age_max_s` and `types` parameters;
  `InventoryIndex.rollup` computes one additional filtered aggregate set per request in
  the same subtree pass (the generalization of the existing `unignored_*` dual
  accumulators). Nodes gain `filtered_files` / `filtered_size` when filters are
  requested; layout weights read them in hide mode.
- `watchRollup` refetches when hide-mode filter values change; dim-mode changes only
  reapply classes.

### API Changes

- `/api/rollup`: optional `age_max_s` (seconds) and `types` (comma-separated logical
  extensions or family names); response nodes carry `filtered_files` / `filtered_size`
  (and a filtered extension-tally column) only when requested.
- `/api/search`: no contract change; used with an empty keyword for hide-mode trees.
- `/api/recent`: no change; its existing `ext_filter` composes with the Recent preset.

## Implementation Plan

### Phase 1: FilterState and the Nav Filter Bar (dim mode)

- [ ] `static/filter_state.js` with persistence, change events, presets, and SDK
  `mb.filters` proxy; vm tests
- [ ] Nav filter bar with Current and Recent chips, the filter menu (age, type,
  visibility, mode, clear), and the active-filter badge; shared chip and menu styles
- [ ] Client-side dim application in tree rendering and store patches; DOM tests for
  chip state, dimming, and persistence
- [ ] Recent chip activates the existing clustered presentation scoped by active filters
  (tab untouched)

### Phase 2: Folder Views on Shared State

- [ ] Migrate the treemap ignored control to `mb.filters`; bind dim mode for age and
  type in cells
- [ ] `rollup()` filtered aggregates plus `/api/rollup` params and wire validators;
  hide-mode relayout and refetch; budget re-measured with filters active
- [ ] Hide mode on the nav via `/api/search` once that endpoint lands (falls back to dim
  until then)

### Phase 3: Retire the Recent Tab

- [ ] Parity checklist: clustering, counts, truncation marks, window switching, live
  updates, and keyboard access all working under the Recent preset
- [ ] Remove the tab; single Files pane with the filter bar; update docs and the design
  system’s panel guidance

## Testing Strategy

- vm tests for `FilterState` (persistence, events, preset semantics, subscribe/dispose)
- DOM tests for chip toggling, menu keyboard access, dim application on tree rows and
  treemap cells, and state sharing between the two surfaces
- Unit tests for filtered rollup aggregates (age and type variants, combined with
  gitignore exclusion) and the extended route validation
- The Phase 3 parity checklist run against the live Recent tab before removal

## Rollout Plan

Phase 1 is additive and client-only; the Recent tab keeps working throughout.
Phase 2 lands server parameters behind optional query strings, so existing clients are
unaffected. Phase 3 removes the tab only after the parity checklist passes in a real
browser session. Filter state stays out of the URL hash (matching the treemap-toggle
decision) in this version.

## Open Questions

- Is **Current** correctly defined as the active tracker’s live files, or should it mean
  something broader (files touched in the last few minutes regardless of tracking)?
- Should filters eventually serialize into the hash for shareable filtered links, or
  stay per-user state?
  (This version: per-user localStorage.)
- Type filter granularity: are the `ft-*` families the right menu unit, with exact
  extensions as a detail level, or should the menu list raw extensions from the index’s
  suffix tally?
- Does the Recent preset default to `24h` (the tab’s default) and does Current imply a
  short age window when no files are actively live?

## References

- [Scalable file search](plan-2026-07-17-scalable-file-search.md) (keyword dimension and
  the hide-mode tree provider)
- [Folder views and the treemap overview](plan-2026-07-20-folder-views-and-treemap-overview.md)
  (the gitignored three-state and filtered-aggregate precedent)
- [Scanning state and recent directories](plan-2026-07-16-scanning-state-and-recent-directories.md)
- [Design system](../../../design-system.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
