# Feature: Unified Filtering Across Navigation and Folder Views

**Date:** 2026-07-20 (last updated 2026-07-31)

**Author:** Metabrowser maintainers

**Status:** Phase 1 implemented; Phases 2 and 3 planned

## Overview

Metabrowser filters files in several unrelated ways today: the Recent tab is an age
filter wearing a tab, the treemap exposes a compact gitignored visibility control, the
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
- A second crawl or required persistent index.
  The scalable-search plan owns the inventory revision and bounded search endpoint
  needed for complete hide mode; `/api/recent` already accepts extension and prefix
  filters.
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
  already consumes, so a Current filter updates live for rows inside the connection’s
  current event scope without new transport.
- Every inventory entry carries `mtime_ns`, `ext`, `gitignored`, and `active`, while
  rendered tree rows carry the equivalent path, time, ignore, and activity state.
  Dim mode needs no new server query for mounted rows.

### Status Review: 2026-07-31

Phase 1 is implemented in the current browser and was closed after the full repository
verification gate and a live browser pass:

- `filter_state.js` owns persisted Current, age, type-family, and gitignored state,
  exposes shared predicates, and publishes changes through `mb.filters`
- the Files pane has Current and Recent chips, an age/type/visibility menu, an active
  count badge, and Clear
- age, type, and Current predicates dim rendered Files rows; hidden gitignored state
  prunes rendered subtrees; inventory changes reapply the decorations
- the treemap shares visibility state, dims age/type non-matches, and reports active
  filters while treating Current as navigation-only
- the existing Recent tab remains separate and unchanged

The scalable part is still missing.
The browser does not have a keyword field, `/api/search`, complete hide-mode projection,
filtered rollup aggregates, or a revision-only signal for deep changes.
Dim mode only evaluates mounted rows, so it cannot discover files in lazy, unmounted
subtrees.

Two correctness seams need explicit coverage before Phase 2:

- `FsEntry.ext` and rollup tallies currently use a physical compound suffix, while file
  opening and tree projection use logical extensions.
  Type filtering is therefore not consistently transparent for `.gz` and `.zlib`
  artifacts.
- the browser event stream uses the depth-two scope.
  Current state and ordinary `fs.change` events for deeper files do not reach a loaded
  deep row or an active search unless the event contract gains a scoped-safe revision or
  expanded-prefix mechanism.

## Design

### Resolved Decisions

Defaults chosen to unblock implementation; each is cheap to change during review.

1. **Current means the active tracker’s live files, exactly.** No hidden fallback to a
   short age window: composing Current with an age filter is explicit in the menu, and a
   fully-dimmed tree when nothing is live is honest.
   Rollup nodes carry no activity flag, so the treemap ignores the activity dimension in
   v1 and its caption says so while Current is on.
2. **Filter state stays out of the URL hash and persists per-user through `mb.prefs`**
   (host-only cookies shared across per-root ports — the spec predates `mb.prefs`;
   localStorage is superseded).
   The nav bar always shows an active-filter badge and a Clear action so persisted
   filters are never invisible state.
3. **The Phase 1 type-menu unit is the `ft-*` family via `mb.fileTypeClass`** — the same
   classifier that colors filenames everywhere.
   The v1 menu lists families only, and a family matches its subtypes (`md` matches
   `md-runbook`). Phase 2 must expand those families through one declarative mapping
   before sending exact logical extensions to a generic server endpoint.
4. **The Recent preset defaults to the tab’s `24h` window**, adjustable in the menu from
   the `RECENT_WINDOWS` set (minus `all`).
5. **v1 has no standalone mode switch: age and type apply as dim everywhere; visibility
   keeps its three-state.** The hide half needs completeness guarantees (filtered rollup
   aggregates server-side; `/api/search` for the nav) and lands in Phase 2. Visibility’s
   `hidden` already has server support (`unignored_*` aggregates in the treemap) and
   applies to the nav as a client-side prune of gitignored subtrees.
   The dense treemap toolbar presents this as one **Show gitignored** checkbox: off
   writes `hidden`, and on writes `shown`. A `dimmed` value selected in the navigation
   menu remains valid shared state and appears checked because ignored entries are still
   present.
6. **Filtering is a decoration layer over the tree, not a render fork.** The nav applies
   filter classes by walking rendered rows (every predicate input — mtime, name,
   gitignored, active — is already on the row), on filter changes and debounced after
   inventory patches. Render paths stay untouched, so no-filter behavior is
   byte-identical to today.
7. **The Recent chip filters the Files tree; the Recent tab is untouched until the Phase
   3 parity checklist passes.** Nothing existing changes shape in Phase 1.

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

Presentation stays per-surface and orthogonal: the Files tree shows dimmed or pruned
rows, the separate Recent tab keeps its recency-clustered list until Phase 3, and the
treemap dims cells or relayouts.

### FilterState (core shell)

- The strict `static/filter_state.js` module exposes `window.MetabrowserFilterState`:
  `get()`, `set(patch)`, `subscribe(listener)`, `clear()`, `activeCount()`, the shared
  predicate helpers (`rowMatches`, `typeMatches`, `windowSeconds`), and the preset
  definitions. State shape:
  `{current: bool, ageWindow: "1h"|"24h"|"7d"|"30d"|null, types: string[]|null, ignored: "shown"|"dimmed"|"hidden"}`
  (no mode field in v1 — Resolved Decision 5).
- Persisted through `mb.prefs` under one versioned key (`filters`); every change
  dispatches a `metabrowser:filter-change` CustomEvent (the `watchRollup` pattern).
- The SDK proxy `mb.filters` (get / set / subscribe) keeps plugin views away from the
  global directly. The treemap’s ignored control now uses this shared dimension instead
  of its private localStorage state.
- A shared chip-row and menu primitive (core styles, reused classes) renders the same
  controls at both densities, so the vocabulary looks identical everywhere.

### Navigation Pane (simplified form)

- A compact filter bar above the tree, outside the replaceable tree container (the
  search spec’s placement rule): `[Current] [Recent] [⏷ filter menu]`, with an active
  count badge on the menu button and a clear affordance when any filter is set.
- The Phase 1 menu holds age window chips (reusing `RECENT_WINDOWS`), type-family
  multi-select, the visibility three-state, and Clear.
  A general dim/hide mode switch appears only after complete server-backed hide mode
  lands.
- Dim mode (default): non-matching rows get the muted treatment client-side; matching
  rows keep their age and size coloring.
  No server round trip.
- Hide mode: the tree renders from `/api/search` with an empty keyword and the active
  ext/age predicates (matches plus ancestors, incompleteness reported) — this phase
  depends on the scalable-search plan’s endpoint and falls back to dim until it lands.
- The Phase 1 Recent chip applies its age predicate to the Files tree.
  The existing recency-clustered presentation remains in the Recent tab until the Phase
  3 parity gate; Current shows live Files rows with the existing activity indicators.
- The Recent tab stays during the transition and retires in Phase 3; the nav header then
  has a single Files pane with the filter bar.

### Folder Views and the Treemap (full form)

- The treemap toolbar separates **encodings** (Metric, Grouping, Color — view-local,
  unchanged) from **filters** (shared state via `mb.filters`). Its single **Show
  gitignored** checkbox maps to the shared visibility state without duplicating the
  navigation menu’s three-state control.
- Dim mode adds the muted cell class to non-matching cells (per-cell `ext` and `mtime`
  are already in the rollup payload; directory cells dim only when their newest mtime or
  dominant type rules them out entirely).
- Hide mode extends `/api/rollup` with `max_age_seconds` and repeated `ext` parameters;
  `InventoryIndex.rollup` computes one additional filtered aggregate set per request in
  the same subtree pass (the generalization of the existing `unignored_*` dual
  accumulators). Nodes gain `filtered_files` / `filtered_size` when filters are
  requested; layout weights read them in hide mode.
- `watchRollup` refetches when hide-mode filter values change; dim-mode changes only
  reapply classes.

### API Changes

- `/api/rollup`: planned optional `max_age_seconds` and repeated `ext` values; response
  nodes carry `filtered_files` / `filtered_size` (and a filtered extension-tally column)
  only when requested.
- `/api/search`: planned by the scalable-search spec and not implemented yet.
  Unified hide mode uses an empty keyword with exact logical-extension and age
  predicates.
- `/api/recent`: no change; its existing `ext_filter` composes with the Recent preset.

## Implementation Plan

### Phase 1: FilterState and the Nav Filter Bar (dim mode)

- [x] `static/filter_state.js` with prefs persistence, change events, presets, shared
  predicates, and the SDK `mb.filters` proxy; vm tests
- [x] Nav filter bar with Current and Recent chips, the filter menu (age, type,
  visibility, clear), and the active-filter badge; shared chip and menu styles
- [x] Decoration-layer filter application over rendered tree rows (dim for age, type,
  activity; subtree prune for hidden gitignored), reapplied on filter changes and
  debounced inventory patches; live-insert rows (`_buildRowHtml`) brought back to parity
  with `renderTreeNodes` (select-dir action + chevron hotspot)
- [x] Treemap binds visibility to the shared state (its toggle writes through) and dims
  cells for age and type; caption reports active filters and the nav-only activity
  dimension

### Phase 2: Complete Hide Mode

- [ ] Normalize logical extension identity across inventory, Recent, suffix metadata,
  rollups, search, and the browser type-family classifier
- [ ] `rollup()` filtered aggregates plus `/api/rollup` params and wire validators;
  hide-mode relayout and refetch; budget re-measured with filters active
- [ ] Add the scalable-search endpoint, public inventory revision, and scoped-safe
  revision invalidation described by the search plan
- [ ] Hide mode on the nav through `/api/search`; do not ship loaded-rows-only hide
  semantics because they cannot distinguish an unmounted match from no match
- [ ] Add nav DOM coverage for chip/menu keyboard behavior, Clear, the active badge,
  live deep-row updates, and compressed logical-type filtering

### Phase 3: Retire the Recent Tab

- [ ] Parity checklist: clustering, counts, truncation marks, window switching, live
  updates, and keyboard access all working under the Recent preset
- [ ] Remove the tab; single Files pane with the filter bar; update docs and the design
  system’s panel guidance

## Testing Strategy

- Existing vm tests cover `FilterState` persistence, events, preset semantics, shared
  predicates, and treemap state sharing
- Add DOM tests for nav chip toggling, menu keyboard access, Clear, active-badge state,
  dim application on tree rows, and compressed logical-type behavior
- Unit tests for filtered rollup aggregates (age and type variants, combined with
  gitignore exclusion) and the extended route validation
- The Phase 3 parity checklist run against the live Recent tab before removal

## Rollout Plan

Phase 1 is additive and client-only; the Recent tab keeps working throughout.
Phase 2 lands server parameters behind optional query strings, so existing clients are
unaffected. Phase 3 removes the tab only after the parity checklist passes in a real
browser session. Filter state stays out of the URL hash (matching the treemap-toggle
decision) in this version.

## Review Notes for the Maintainer

The former open questions are answered in Resolved Decisions 1–4 with defaults chosen
for predictability; all four are one-line changes if review says otherwise:

- Current = tracker-live only (no implicit age fallback) — Decision 1
- Filters stay out of the hash; `mb.prefs` persistence with a visible badge — Decision 2
- Type menu lists `ft-*` families; Phase 2 must map them to exact logical extensions —
  Decision 3
- Recent preset defaults to `24h` — Decision 4

Still genuinely open (deferred, not blocking Phase 1):

- Phase 2: whether type-family expansion remains browser-owned or moves to a shared
  declarative table. The search API should stay generic and accept exact logical
  extensions.
- Phase 3: the clustered presentation’s exact styling under the Recent preset

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
