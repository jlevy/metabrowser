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
- the filename’s extension, plus `MetabrowserFileTypes.classFor` for the `ft-*` hue that
  colors it
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
5. **Filtering hides; there is no dim/hide switch.** Removing what does not match is
   what filtering *is*, so offering “dim instead” was offering to not do the thing the
   user asked for. Hiding never claims completeness it does not have: pruning keeps
   folders whose contents are not loaded and renders a footer note counting them.
   Gitignored entries keep the dimmed treatment the tree has always given them, which is
   the one place dimming still earns its place.
6. **Gitignored is one checkbox, not a three-state.** Shown-and-dimmed is the default
   and the only visible state; unchecking removes those rows entirely.
   The former `shown` value (visible and *un*-dimmed) bought nothing that the dimmed
   default does not already give, and “Shown / Dimmed / Hidden” sitting next to a “Hide
   / Dim” treatment group was two adjacent controls with near-identical vocabulary.
7. **Recency reads from `/api/recent` whenever a window is set.** This is the whole
   answer to the reach problem in Background, and it is the normal path rather than a
   corner: clicking a recency chip gives the Recent tab’s exact behavior inside the
   Files pane. The Files tree renders `/api/recent?window=`'s tree through the same
   `renderTreeNodes`, keeping the endpoint’s totals and truncation reporting.
   `live` stays on the tree source — the endpoint has no window for the active tracker’s
   files.
8. **Filter state persists through `mb.prefs` and stays out of the URL hash.** Same
   choice the treemap branch made, for the same reason: filters are a view preference,
   not an address. Persisted state is never invisible — the badge and Clear are always
   present when anything is set.
9. **Type filtering is by literal extension, offered from what the tree contains.** The
   menu lists real extensions (`.md`, `.py`, `.ts`) rather than abstract `ft-*`
   families, ranked by frequency, capped at 30, each row carrying its tally.
   Tallies come from the known-file catalog — the complete index the quick-file palette
   already searches — so the counts cover the whole tree rather than the expanded
   subset, and the menu can never offer a type with nothing behind it.
   Rows keep their `--ft-color`, so a menu row and the filenames it keeps read in the
   same hue.
10. **Size is a cumulative floor, not a band.**
    `Any / >100K / >1M / >10M / >100M / >1G`. “What is over 10M in here” is the question
    people ask; bands make you guess which one a file landed in.
11. **The drawer carries no section headings.** An extension menu, a size ramp, and a
    checkbox labelled “Gitignored” already say what they are, and four uppercase labels
    cost more vertical space in a 300px pane than they were paying for.
12. **The tab bar survives with one tab.** The user-visible ask is a Files pane that
    never needs switching.
    Keeping `.tab-bar.nav-tab-bar` with a single Files tab preserves the pane header’s
    shape and shadow behavior and leaves the seam for a future second pane, at the cost
    of one vestigial-looking control.
13. **The nav tally splits tracked from ignored.**
    `282 files (3.6 MB) + 12,300 ignored (186.2 MB)`, with the ignored half muted to
    match how those rows read below.
    A single combined figure hid that almost all of a repository’s bytes are build
    output. The split cannot be derived by summing top-level children — ignored files
    nested under tracked directories would count as tracked — so
    `InventoryIndex.root_summary()` computes it in one pass and `/api/tree` carries it.

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
  recency: "all" | "live" | "1h" | "24h" | "7d" | "30d",   // default "all"
  types: string[] | null,                                  // extensions (".md"), null = any
  size: "all" | "100k" | "1m" | "10m" | "100m" | "1g",     // default "all"; a floor
  showIgnored: boolean,                                    // default true (visible, dimmed)
}
```

The module owns `get`, `set(patch)`, `clear`, `subscribe`, `activeCount`, and the shared
predicates `rowMatches`, `typeMatches`, and `sizeMatches`, so the tree and any future
surface can never disagree about what matches.
Persistence rides `mb.prefs` under one versioned `filters` key; every change dispatches
`metabrowser:filter-change` alongside the subscriber callbacks.

Missing data never rules a row out: an absent mtime or a pending size is incomplete
information, not a non-match, and pending rows must not flicker as filtered.
A missing *extension* is the deliberate exception — “this file has no extension” is
complete information, so `Makefile` is a real non-match for a `.md` filter.

This is the treemap branch’s `filter_state.js` with `current` and `ageWindow` folded
into `recency`, `size` added, and its `ignored` three-state reduced to a boolean; that
branch rebases onto this module rather than carrying its own.

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

Expanded, the drawer adds three unlabelled controls — each says what it is:

```
├─────────────────────────────────────────────┤
│ ⟨All│Live│1h│1d│1w│1mo⟩          Less  ②   │
│ [Any type ⌄]  [✓ Gitignored]                │  dropdown + checkbox
│ ⟨Any│>100K│>1M│>10M│>100M│>1G⟩              │  single-select, a floor
│                                   Clear all │
├─────────────────────────────────────────────┤
```

The extension dropdown opens over the shared `.menu` surface, ranked by frequency and
capped at 30, each row tallied and tinted with its file-type hue:

```
   ✓ Any type
     .py      156
     .js       43
     .md       33
     .toml     10
```

Clear resets every dimension including the ones in the collapsed row, and the drawer’s
open state is itself a preference, so a user who lives in type filters is not re-opening
it every session.

### The Nav Tally

The header row above the tree splits tracked from ignored, with the ignored half muted
to match how those rows read below it:

```
282 files (3.6 MB) + 12,300 ignored (186.2 MB)
```

`InventoryIndex.root_summary()` computes both halves in one pass over the index and
`/api/tree` carries them on the full-tree request only.
The per-directory `total_files` / `total_size` aggregates stay gitignore-blind — a
folder’s size is its size — which is exactly why the split needs its own pass rather
than a sum over top-level children.

The walker’s root upsert can only refresh the blind aggregate, so the split row owns
separate classes (`.tree-summary-tracked`, `.tree-summary-ignored`) and its own
debounced refresh; otherwise the live patch would overwrite the tracked half with the
combined total.

### Applying Filters

Filtering is a decoration layer over rendered rows, never a render fork.
The no-filter DOM stays byte-identical to today, which is what keeps this change
reviewable.

- Non-matching file rows are pruned, along with folders that have no loaded match; a
  footer note counts the folders that are not expanded, so the pruned tree never implies
  completeness it does not have.
- A **recency window** swaps the tree’s data source to `/api/recent?window=` per
  Resolved Decision 7, rendered by `renderTreeNodes` with the existing truncation
  banner. Type and size then prune over that result, so the endpoint stays a recency
  query and the client owns the rest.
- **Gitignored** rows keep the tree’s existing dimmed treatment when shown; unchecking
  prunes those subtrees.
- A hidden folder’s verdict propagates to its descendants, so a pruned subtree never
  keeps an orphaned visible row under a parent that is gone.

Reapplication is driven by `metabrowser:filter-change` and, debounced, by inventory
patches; newly inserted live rows are classified on insert.

### Retiring the Recent Tab

The tab, its panel, `renderRecentControls`, and `setActiveRecentChip` come out.
`/api/recent`, `recent.py`, `recentBaseEntries`, the live overlay, and the clustered
presentation all stay — they become the data path for a recency window, not a separate
place.

## Implementation Plan

Checked items are implemented and covered by tests; `make verify` passes on the branch.

### Phase 1: The Control Family — done

- [x] Core `styles.css` section for `.chip`, `.chip-group[data-select]`, `.chip-toggle`,
  `.chip-menu`, `.chip-badge`, `.chip-clear`, with light and dark token coverage and no
  color literals
- [x] `static/filter_controls.js` producing group markup with correct ARIA per variant,
  plus shared click, keyboard, and dropdown-dismissal handling
- [x] `docs/design-system.md` gains a Filter Controls section stating the single-select
  and multi-select fill convention, the one-mechanism rule, and the dropdown contract
- [x] `.recent-chip` deleted

### Phase 2: Filter State and the Bar — done

- [x] `static/filter_state.js` under the strict `tsconfig.json` gate, with prefs
  persistence, change events, `activeCount`, and the shared predicates
- [x] `mb.prefs` and `mb.filters` SDK surfaces with safe no-ops when absent
- [x] The filter bar and drawer in the shell HTML, wired to the state, with the badge,
  Clear, and persisted drawer state
- [x] Extension dropdown built from known-file-catalog tallies, ranked and capped

### Phase 3: Applying Filters to the Tree — done

- [x] Pruning with folder retention and the unloaded-folders footer note
- [x] A recency window backed by `/api/recent`, reusing the truncation banner, with type
  and size pruning over that result
- [x] Gitignored checkbox replacing the unconditional fade
- [x] Reapplication on filter change and debounced after inventory patches

### Phase 4: One Files Pane — done

- [x] Tab removal, single Files pane, docs updated
- [x] `InventoryIndex.root_summary()` plus the `/api/tree` `summary` field and the split
  nav tally

### Phase 5: Follow-ups — open

- [ ] Extension tallies exclude gitignored files, because `catalog_files()` filters them
  out; with **Gitignored** checked the tree shows rows the menu did not count
- [ ] Decide whether `Live` earns a segment (see Open Questions)
- [ ] The folder-treemap branch rebases onto the core family and the shared state

## Testing Strategy

Implemented:

- vm tests (`tests/dom/filter_controls_behavior.js`) for each control variant:
  single-select exclusivity, multi-select accumulation and empty-set normalization,
  `aria-pressed` / `aria-checked` correctness, roving tabindex, dropdown summarisation
  and row state, and HTML escaping
- vm tests (`tests/dom/filter_state_behavior.js`) for `FilterState`: defaults,
  sanitization of malformed persisted values, `activeCount`, event and subscriber
  delivery, unsubscribe, snapshot isolation, the cumulative size floor, and extension
  matching
- Predicate tests asserting that a missing mtime or pending size never excludes a row,
  and that a missing extension does
- Structural tests (`tests/test_browser_filter_ui.py`) pinning the fill convention, the
  ARIA-to-styling coupling, the token-only rule, and the no-filter DOM guard
- Unit tests (`tests/test_inventory_root_summary.py`) for the tracked/ignored split,
  including ignored files nested under tracked directories

Still owed:

- A live-browser pass over keyboard traversal of the dropdown (arrow keys inside the
  menu itself, as opposed to the chip groups)

## Rollout Plan

Phases 1 and 2 are additive: an all-default filter state changes nothing about the
rendered tree. Phase 3 changes appearance only when a filter is set.
Phase 4 removes the Recent tab, which is the one irreversible step.

The folder-treemap branch rebases onto this and drops its private `.tm-seg`,
`.tm-check`, `.filter-chip`, and `filter_state.js` in favor of the core family; its
toolbar keeps its view-local encodings (Metric, Grouping, Color, Depth) and binds its
gitignored control to the shared dimension.
Its `current` + `ageWindow` pair collapses to `recency`, and its `ignored` three-state
to `showIgnored`.

## Open Questions

**Does `Live` earn its segment?** It is not a synonym for `1h`: the active tracker marks
a file live when its size or mtime fingerprint changed within `stale_after_s` (30s),
plus up to `ACTIVE_TRACKER_QUIET_POLLS × ACTIVE_TRACKER_INTERVAL_S` (30s) of hysteresis
— so roughly “changed in the last half-minute”, two orders of magnitude narrower than
`1h`. It is also the only recency value that updates live over SSE without a refetch,
which is what makes it useful while watching an agent write logs.

Against it: on a quiet repository it is always empty, which reads as broken rather than
as “nothing is happening”, and it is the same *kind* of thing as the windows beside it.
The alternative is to relabel it `30s` and make the axis uniform, at the cost of losing
the “this updates in real time” connotation.

**Should the extension tallies include gitignored files?** `catalog_files()` excludes
them, so with **Gitignored** checked the tree shows rows the menu never counted.
Fixing it means either widening the catalog feed or tallying from a second source.

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
