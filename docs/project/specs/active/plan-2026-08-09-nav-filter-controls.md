# Feature: Filter Controls and Fine-Grained Navigation Filtering

**Date:** 2026-08-09

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

The navigation pane splits browsing across two tabs that are really one thing.
Files shows the tree; Recent shows the same rows with an age filter applied and a window
picker on top. Switching tabs to answer “which markdown did I touch this week” is a mode
change where a filter would do.

Meanwhile the repository has four near-identical pill controls that nothing shares:
`.recent-chip` in core styles, and `.tm-seg`, `.tm-check`, plus a second `.filter-chip`
on the folder-treemap branch.
Each was written for one surface and none can express a multi-select group.

This plan does two things at once, because neither is worth doing alone.
It promotes one filter-control family into core styles — a single chip atom, joined
single-select and multi-select groups, standalone toggles, a count badge, and a clear
affordance — and it uses that family to replace the Files/Recent tab pair with a single
Files pane carrying an always-visible filter bar and an expandable drawer for the long
tail.

## Goals

- Define one control family in core `styles.css` covering single-select, multi-select,
  and boolean filters, so every surface that filters looks and behaves the same
- Retire `.recent-chip`, and give the folder-treemap branch’s `.tm-seg` / `.tm-check` /
  `.filter-chip` a core home to rebase onto rather than three private copies
- Make single-select and multi-select visually distinguishable before the user clicks
- Replace the Files/Recent tab pair with one Files pane; the Recent tab’s job becomes
  the recency dimension of the filter bar
- Filter the navigation tree by recency, file type, size, and gitignored status, with
  the common controls always visible and the rest one toggle away
- Keep filters visible and reversible: a count badge whenever anything is set, and a
  Clear that returns every dimension to its default
- Preserve what the Recent tab does better than a client-side filter — its reach past
  the loaded subtrees — rather than quietly narrowing it

## Non-Goals

- Content or keyword search; that is the
  [scalable file search](plan-2026-07-17-scalable-file-search.md) plan’s dimension of
  the same vocabulary, and this plan leaves room for it rather than implementing it
- Saved or user-named filter combinations
- Filtering inside document views; a rendered README ignores filters
- Folder-view and treemap filtering; this plan gives that work a shared vocabulary and
  shared controls to adopt, and the
  [folder views and treemap](https://github.com/jlevy/metabrowser/pull/23) branch adopts
  them on rebase
- New crawls or index changes; every predicate reads data already on the wire

## Background

### What the rendered tree already knows

Every predicate this plan needs is on the row before any filter runs:

- `data-tip-mtime` — modification time in seconds, on file and folder rows
- `data-tip-size` — bytes on file rows, subtree bytes on folder rows
- `data-logical-ext` plus `MetabrowserFileTypes.classFor` — the `ft-*` family that
  already colors the filename
- `.tree-item-gitignored` — the class the tree sets today
- `.activity-dot` — the live-file marker from the active tracker

So recency, type, size, and gitignored filtering over loaded rows costs one DOM walk and
no server support. This is what makes an always-visible filter bar affordable.

### What the Recent tab does that a DOM walk cannot

`/api/recent` scans the whole inventory index, not the loaded subtrees.
It answers “what changed in the last hour anywhere under the root”, reports
`total_matching` and `truncated` honestly, and clusters results by recency.
A client-side age filter over rendered rows sees only what has been expanded.

Retiring the tab without addressing this trades a complete answer for a partial one.
The design below keeps the endpoint and changes only which pane presents it.

### What the treemap branch already got right

The folder-treemap branch’s toolbar is the visual target.
`.tm-seg` is a bordered pill wrapping borderless buttons split by hairline rules, active
segment filled, whole group reading as one object.
It is built from tokens with no color literals, it is keyboard-reachable, and the
segments stay legible at 12px. The gap is that it exists once per surface, expresses
single-select only, and lives in a plugin stylesheet.

## Design

### Resolved Decisions

Defaults chosen to unblock implementation; each is cheap to change during review.

1. **Recency is one dimension, not two.** Live (the active tracker’s flag) becomes the
   leading segment of the recency group rather than a separate Current chip, because
   “live” is the narrowest point on the same axis and “live but older than a week” is
   not a query anyone wants.
   One `recency` field replaces the treemap branch’s separate `current` and `ageWindow`.
2. **Single-select fills with accent, multi-select fills with neutral.** A selected
   single-select segment takes `--highlight-bg` with `--link` text — the treatment
   `.menu-seg[aria-checked]` already uses for the theme picker.
   A selected multi-select chip takes `--hover-bg` with `--text` and medium weight.
   The distinction is inherited from an existing convention, not invented, and it reads
   before the first click.
3. **Every control is a `<button aria-pressed>`.** The treemap branch’s `.tm-check`
   wraps a real checkbox and keys off `:has(input:checked)`; that is a second way to
   read state for no gain in a control that never posts a form.
   One mechanism means one place to read state in tests.
4. **The drawer is inline, not a floating menu.** It expands in place below the filter
   bar and pushes the tree down.
   A 300px pane cannot host a comfortable floating panel, and an inline drawer keeps
   active filters and their controls in the same visual column.
   Floating menus stay for the header settings.
5. **Hide is the default treatment; Dim is the escape hatch.** Setting a filter removes
   what does not match, because that is what “filter” means to the person clicking it —
   a type filter that leaves every file in place, faded, has not answered the question.
   Dim stays one segment away for the case where the tree’s shape is the point.
   Hide never claims completeness it does not have: pruning keeps folders whose contents
   are not loaded and renders a footer note counting them.
6. **Recency reads from `/api/recent` whenever it is set and the mode is Hide.** This is
   the whole answer to the reach problem in Background, and with Hide as the default
   (Decision 5) it is the normal path, not a corner: clicking a recency chip gives the
   Recent tab’s exact behavior inside the Files pane.
   The Files tree renders `/api/recent?window=`'s tree through the same
   `renderTreeNodes`, keeping the endpoint’s totals and truncation reporting.
   Dim mode decorates loaded rows instead, with no round trip.
   The Recent tab is then redundant in the strict sense, not the approximate one.
7. **Filter state persists through `mb.prefs` and stays out of the URL hash.** Same
   choice the treemap branch made, for the same reason: filters are a view preference,
   not an address. Persisted state is never invisible — the badge and Clear are always
   present when anything is set.
8. **Type filtering uses the `ft-*` families through `MetabrowserFileTypes.classFor`.**
   The same classifier that colors filenames, so a filter can never disagree with the
   colors, and a family matches its subtypes (`md` matches `md-runbook`). Type chips
   carry their own `--ft-color`, making the chip row a legend for the tree.
9. **The tab bar survives with one tab.** The user-visible ask is a Files pane that
   never needs switching.
   Keeping `.tab-bar.nav-tab-bar` with a single Files tab preserves the pane header’s
   shape and shadow behavior and leaves the seam for a future second pane, at the cost
   of one vestigial-looking control.

### The Control Family

Promoted into core `styles.css` as one section, replacing four private copies.

`.chip` is the atom: a pill with a 1px `--viz-border`, `--viz-surface` background,
`--muted` text at `--ui-small-font-size`, `aria-pressed` for state, and a
`:focus-visible` outline in `--link`.

`.chip-group` is the joined container: one shared border and pill radius,
`overflow: hidden`, children losing their own border and gaining a hairline
`--viz-border-subtle` divider between siblings.
The group’s selection semantics are declared, not implied:

| Variant | ARIA | Behavior | Selected fill |
| --- | --- | --- | --- |
| `.chip-group[data-select="one"]` | `role="radiogroup"`, `aria-checked` | Exactly one active; clicking the active segment is a no-op | `--highlight-bg` / `--link` |
| `.chip-group[data-select="many"]` | `role="group"`, `aria-pressed` | Each segment independent; none-selected means no constraint | `--hover-bg` / `--text` |

`.chip-toggle` is a standalone boolean chip outside any group — the same atom, not
joined, `aria-pressed`.

`.chip-badge` is the count pill that rides a chip, in `--link` on `--bg` with tabular
numerals.
`.chip-clear` is a quiet borderless text button in `--link`, rendered only when
something is set, because a permanently visible Clear on a clean state is noise.

Wrapping is the group’s responsibility: `.chip-group` wraps at the container edge and
the dividers survive wrapping, so the type row degrades gracefully in a narrow pane.

Keyboard behavior follows the ARIA pattern the variant declares — arrow keys move within
a radiogroup and Tab enters and leaves it; every chip in a `many` group is its own tab
stop.

### Filter State

New strict module `static/filter_state.js` exposing `window.MetabrowserFilterState`,
with an `mb.filters` SDK proxy so plugin views never touch the global:

```js
{
  recency: "all" | "live" | "1h" | "24h" | "7d" | "30d",  // default "all"
  types: string[] | null,                                  // ft-* families, null = any
  size: "all" | "s" | "m" | "l",                          // default "all"
  ignored: "shown" | "dimmed" | "hidden",                 // default "dimmed"
  mode: "dim" | "hide",                                    // default "hide"
}
```

The module owns `get`, `set(patch)`, `clear`, `subscribe`, `activeCount`, and the shared
predicates `rowMatches` and `typeMatches`, so the tree and any future surface can never
disagree about what matches.
Persistence rides `mb.prefs` under one versioned `filters` key; every change dispatches
`metabrowser:filter-change` alongside the subscriber callbacks.

Missing data never rules a row out.
An unclassified path, an absent mtime, or a pending size is incomplete information, not
a non-match — pending rows must not flicker as filtered.

This is the treemap branch’s `filter_state.js` with `current` and `ageWindow` folded
into `recency` and `size` and `mode` added; that branch rebases onto this module rather
than carrying its own.

### The Navigation Filter Bar

The bar sits between `.nav-tab-bar` and `.tree-content`, outside the replaceable
`#tab-files` container so a tree reload never destroys it, and above the scroll owner so
it never scrolls away.
The nav bar’s `.scrolled` shadow moves to the bar’s bottom edge.

Always visible, one row in a 300px pane:

```
┌─────────────────────────────────────────────┐
│ Files                                       │  .nav-tab-bar
├─────────────────────────────────────────────┤
│ ⟨All│Live│1h│1d│1w│1mo⟩        ⌄ More  ②   │  .filter-bar
├─────────────────────────────────────────────┤
│ ▸ src/                                      │  .tree-content
```

The recency group is single-select and always present; it is the Recent tab’s window
picker, promoted. Values stay `1h`/`24h`/`7d`/`30d` to match `RECENT_WINDOWS` and the
endpoint; labels shorten to `1h`/`1d`/`1w`/`1mo` to fit the pane.
`More` is a `.chip-toggle` carrying the active-filter `.chip-badge`.

Expanded, the drawer adds labeled rows:

```
├─────────────────────────────────────────────┤
│ ⟨All│Live│1h│1d│1w│1mo⟩        ⌃ More  ②   │
│ TYPE                                        │
│ ⟨md│code│data│config│text│other⟩            │  multi-select, ft-tinted
│ SIZE                                        │
│ ⟨Any│<10 KB│10 KB–1 MB│>1 MB⟩               │  single-select
│ GITIGNORED                                  │
│ ⟨Shown│Dimmed│Hidden⟩                       │  single-select
│ NON-MATCHING                                │
│ ⟨Dim│Hide⟩                                  │  single-select
│                                   Clear all │
├─────────────────────────────────────────────┤
```

Clear resets every dimension including the ones in the collapsed row, and the drawer’s
open state is itself a preference, so a user who lives in type filters is not re-opening
it every session.

### Applying Filters

Filtering is a decoration layer over rendered rows, never a render fork.
The no-filter DOM stays byte-identical to today, which is what keeps this change
reviewable.

- **Hide** (default) prunes non-matching file rows and folders with no loaded match,
  then renders a footer note counting unloaded folders, so the pruned tree never implies
  completeness it does not have.
- **Recency under Hide** swaps the tree’s data source to `/api/recent?window=` per
  Resolved Decision 6, rendered by `renderTreeNodes` with the existing truncation
  banner. Type and size then apply as a prune over that result, so the endpoint stays a
  recency query and the client owns the rest.
- **Dim** adds a muted class to non-matching rows instead of pruning.
  Folders dim only when nothing under them can match — an unloaded folder is unknown,
  not excluded.
- **Gitignored** keeps its three-state independent of `mode`: `shown` lifts the tree’s
  default fade, `dimmed` is today’s behavior, `hidden` prunes those subtrees.

Reapplication is driven by `metabrowser:filter-change` and, debounced, by inventory
patches; newly inserted live rows are classified on insert.

### Retiring the Recent Tab

The tab, its panel, `renderRecentControls`, `setActiveRecentChip`, and the
`recent`-specific tab-switching branches come out.
`/api/recent`, `recent.py`, `recentBaseEntries`, the live overlay, and the clustered
presentation all stay — they become the Hide-mode data path for recency, not a separate
place.

Removal happens only after a parity checklist passes against the live tab: window
switching, counts, truncation marks, live updates under an active filter, and keyboard
access.

## Implementation Plan

### Phase 1: The Control Family

- [ ] Core `styles.css` section for `.chip`, `.chip-group[data-select]`, `.chip-toggle`,
  `.chip-badge`, `.chip-clear`, with light and dark token coverage and no color literals
- [ ] A small render helper producing group markup with correct ARIA per variant, plus
  the shared click and keyboard handling
- [ ] `docs/design-system.md` gains a Filter Controls section stating the single-select
  and multi-select fill convention and the one-mechanism rule
- [ ] `.recent-chip` migrated to the new family and its rules deleted

### Phase 2: Filter State and the Bar

- [ ] `static/filter_state.js` under the strict `tsconfig.json` gate, with prefs
  persistence, change events, `activeCount`, and the shared predicates
- [ ] `mb.filters` SDK proxy with safe no-ops when the module is absent
- [ ] The filter bar and drawer in the shell HTML, wired to the state, with the badge,
  Clear, and persisted drawer state

### Phase 3: Applying Filters to the Tree

- [ ] Hide-mode pruning (the default) with folder retention and the unloaded-folders
  footer note
- [ ] Recency under Hide backed by `/api/recent`, reusing the truncation banner, with
  type and size pruning over that result
- [ ] Dim decoration for recency, type, and size over rendered rows, reapplied on filter
  change and debounced after inventory patches
- [ ] Gitignored three-state replacing the unconditional fade

### Phase 4: One Files Pane

- [ ] Parity checklist against the live Recent tab
- [ ] Tab removal, single Files pane, docs updated

## Testing Strategy

- DOM tests for each control variant: single-select exclusivity, multi-select
  independence, `aria-pressed` and `aria-checked` correctness, keyboard traversal, and
  focus-visible reach
- vm tests for `FilterState`: defaults, sanitization of malformed persisted values,
  `activeCount`, event and subscriber delivery, and unsubscribe
- Predicate tests asserting that missing mtime, size, or classification never excludes a
  row
- DOM tests for dim classification, hide pruning with folder retention, the unloaded
  footer note, and the gitignored three-state
- A test asserting the no-filter DOM is unchanged from today, which is the guard on
  “decoration layer, not render fork”
- The Phase 4 parity checklist run in a real browser session before the tab is removed

## Rollout Plan

Phases 1 and 2 are additive: the control family and the bar land while the Recent tab
keeps working, and an all-default filter state changes nothing.
Phase 3 changes tree appearance only when a filter is set.
Phase 4 is the only irreversible step and it waits on the parity checklist.

The folder-treemap branch rebases after Phase 2 and drops its private `.tm-seg`,
`.tm-check`, `.filter-chip`, and `filter_state.js` in favor of the core family; its
toolbar keeps its view-local encodings (Metric, Grouping, Color, Depth) and binds its
gitignored control to the shared dimension.

## Open Questions

- Whether the drawer’s Dim / Hide control should be per-dimension rather than global,
  once there is usage evidence that recency and type want different treatments
- Whether the type families in the drawer should be fixed or reflect only the families
  actually present under the current root

## References

- [Design system](../../../design-system.md)
- [Scalable file search](plan-2026-07-17-scalable-file-search.md) (the keyword dimension
  of the same vocabulary)
- [Scanning state and recent directories](plan-2026-07-16-scanning-state-and-recent-directories.md)
- [Folder views, treemap, and unified filtering](https://github.com/jlevy/metabrowser/pull/23)
  (the control styling this plan promotes, and the branch that rebases onto it)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
