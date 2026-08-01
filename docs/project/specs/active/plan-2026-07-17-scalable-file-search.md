# Feature: Scalable File Search

**Date:** 2026-07-17 (last updated 2026-07-31)

**Author:** Metabrowser maintainers

**Status:** Draft; prerequisite browser infrastructure is partially implemented

## Overview

Metabrowser should provide a keyboard-first file filter without delaying first paint or
requiring the browser to materialize the complete served tree.
Search queries the existing bounded inventory and reports when that inventory is
incomplete.

## Goals

- Focus search with a documented keyboard shortcut that does not intercept typing in an
  input, editor, or content-editable surface
- Match served-root-relative file paths by case-insensitive keyword
- Filter by logical extension and modification-age window
- Combine keyword, extension, and recency predicates predictably
- Preserve directory hierarchy and stable child order while showing the ancestors of
  every match
- Keep initial navigation lazy and independent of full-root search readiness
- Report indexed counts, limits, and truncation with every result set
- Reuse `InventoryIndex`, logical-extension handling, ignore rules, and live-event
  invalidation instead of adding a second filesystem crawl

## Non-Goals

- Searching inside file contents
- Blocking startup on a complete index
- Rendering every indexed entry in the DOM
- Requiring a database, external search daemon, or native extension for the first
  implementation
- Hiding incomplete results when an inventory cap has been reached

## Background

Metabrowser already builds a bounded `InventoryIndex`, exposes lazy tree navigation, and
reports live filesystem changes.
Logical extensions are normalized at several file and tree response boundaries, but the
inventory’s `FsEntry.ext` still records the physical compound tail, such as `.md.gz`.
Search should compose the existing contracts after logical file identity is made
consistent at the inventory boundary.
A separate crawl or complete tree copy in the browser would duplicate state, increase
startup work, and make truncation harder to report honestly.

### Status Review: 2026-07-31

The current browser has implemented several prerequisites since this plan was written.
It has not implemented path search itself.

| Capability | Current State | Planning Consequence |
| --- | --- | --- |
| Bounded inventory | Implemented: eager asynchronous scan, live updates, file and depth caps | Search can query in-memory metadata without a second crawl |
| Lazy navigation | Implemented: bounded initial depth, lazy subtree requests, and paged DOM insertion | Search results can use the existing tree renderer without changing first paint |
| Index status | Implemented: `/api/index/progress`, `/api/index/meta`, and visible tree truncation | Search should reuse the same status vocabulary and counters |
| Server-side filters | Partial: `/api/recent` supports age, extension, prefix, limits, and result truncation | Predicate and response-shaping patterns exist, but keyword search and ancestor projection do not |
| Shared filter state | Phase 1 implemented: Current, Recent, type, and gitignored controls decorate loaded Files rows and treemap cells | Keyword and hide mode should extend this vocabulary rather than add independent filter state |
| Search API and UI | Not implemented | There is no `/api/search`, keyword input, focus shortcut, result tree, or search-specific empty state |
| Search invalidation | Not implemented | Per-path write generations are internal, and the browser’s depth-two event scope omits deep changes |
| Logical file type | Partial | Compressed files can be classified correctly when opened, but inventory extension filters and type-family filters are not consistently compression-transparent |
| Persistent metadata | Not implemented and not yet justified | Keep it outside the first delivery and require measurements before adding it |

The Current and Recent chips are therefore useful client-side filters, not substitutes
for this feature. They only decorate rows already rendered in the Files tree and cannot
find a matching file in an unmounted deep subtree.

## Design

### Approach

Take a consistent snapshot from `InventoryIndex` and evaluate it in a focused search
service, off the event-loop request path.
Expose the result through one bounded endpoint.
The browser renders matching files and their ancestors in a separate result panel so the
normal Files tree, its expansion state, and its selection remain mounted.

Keyword, extension, and recency predicates combine with AND. Repeated extension values
combine with OR. Extensions use Metabrowser’s logical extension, so transparent
compression does not create separate `.gz` or `.zlib` facets.

### Resolved Decisions

- The first version uses case-insensitive substring matching and the Files tree’s stable
  directory-first path order.
  It does not add fuzzy matching or relevance tiers.
- A result limit applies to matching file leaves.
  Ancestor nodes are additional but remain bounded by the inventory depth cap times the
  leaf limit.
- Obsolete browser requests are aborted and their responses ignored.
  Server work stays off the event loop and bounded; cooperative server cancellation is
  added only if measurements show that aborted scans consume material work.
- Persistent metadata is not part of the first implementation.
  A secondary in-memory path index or persisted stat cache requires evidence from the
  large-root benchmarks.
- An empty keyword is valid so unified-filter hide mode can query extension and age
  predicates without inventing a second endpoint.

### Components

- `InventoryIndex` exposes a consistent entry snapshot, public inventory revision,
  completion state, indexed counts, and configured caps
- A focused search service evaluates keyword, logical-extension, and recency predicates
  and projects matching files plus ancestors without re-statting files
- The search route validates bounded queries and returns matches, ancestors, inventory
  state, and result-limit metadata
- `FilterState` gains the transient keyword dimension; a search controller owns
  debounce, request cancellation, response-revision checks, and the result panel
- `/api/events` publishes a lightweight revision change across every connection scope;
  an active search debounces a refresh when that revision advances

The search control remains outside the replaceable tree-content container so inventory
updates cannot discard focus or the current query.
Search results use a sibling panel rather than replacing the Files panel.
Typing is debounced and cancels an obsolete request.
An active query uses shared design tokens for its filtered-state and incomplete-result
indicators.

The browser must not open an `all-known` event stream to refresh search.
That scope’s initial snapshot can contain the full inventory, violating the requirement
that the browser not materialize the served tree.
A revision-only event provides invalidation without transferring deep entry payloads.

### API Changes

The first implementation adds a bounded endpoint with semantics equivalent to:

```text
GET /api/search?q=report&ext=.md&max_age_seconds=86400&limit=500
```

The response contains:

- a filtered tree containing matching file entries and the ancestor directories needed
  to display them
- the monotonic inventory revision used for the query
- normalized query values and the returned and total match counts
- indexed file and directory counts, the configured file cap, and inventory completion
  or truncation state
- the result limit and an indication that additional matches were omitted

Paths remain served-root-relative.
The route only examines entries already admitted by the inventory, so query text is
never resolved as a filesystem path.
It applies the same visibility and ignore policy as `/api/tree` and must not trigger
traversal or `stat()` calls on the request path.

Named settings bound keyword length, extension count, age range, result count, and
response nodes. The initial defaults should align with the existing 200-row tree page;
the maximums remain provisional until the large-root measurements are recorded.

## Implementation Plan

### Phase 0: Align Existing Prerequisites

- [x] Build the eager bounded inventory, index progress/meta envelopes, lazy tree, and
  live event plane
- [x] Add shared client filter state and the Current, Recent, type, and visibility
  controls in dim mode
- [ ] Store or derive one canonical logical extension on every inventory entry so
  search, Recent, suffix tallies, treemap rollups, and browser type families agree for
  plain, gzip, and zlib artifacts
- [ ] Add a monotonic public inventory revision and a revision-only event that survives
  event-scope filtering without sending deep entry snapshots

### Phase 1: Bounded Search Service and Route

- [ ] Define and test query and response models against a deterministic inventory
- [ ] Add the pure predicate and ancestor-projection service over an inventory snapshot
  without re-statting files
- [ ] Add `/api/search` validation, off-event-loop execution, stable ordering, revision
  checks, and separate inventory-truncation and result-limit metadata
- [ ] Centralize the mapping from the browser’s `ft-*` type families to logical
  extensions so hide mode can send exact, generic extension predicates
- [ ] Measure query latency, snapshot allocation, payload size, and response-node count
  at and beyond the configured inventory cap

### Phase 2: Browser Search and Unified Hide Mode

- [ ] Add the keyboard shortcut, search control, result-tree state, and accessible empty
  and incomplete states
- [ ] Preserve the mounted Files tree while search results are active, and restore it
  without rebuilding or losing expansion and selection state
- [ ] Abort obsolete requests, reject stale revisions, and refresh active results from
  revision events without opening an `all-known` event snapshot
- [ ] Exercise focus, keyboard handling, navigation, live refresh, and tree restoration
  in DOM and real-browser tests

### Phase 3: Evidence-Gated Indexing Changes

- [ ] Evaluate a secondary in-memory path index only if bounded scans miss the query
  latency budget
- [ ] Evaluate persisted stat metadata only if measured warm-start or capacity costs
  justify its invalidation, versioning, and supply-chain complexity

## Testing Strategy

- Unit-test predicate composition, logical extensions, type-family expansion, limits,
  ordering, ancestor projection, and inventory revision changes
- Test the route against traversal attempts, malformed limits, truncated inventories,
  stale revisions, aborted clients, and concurrent filesystem changes
- Exercise focus, keyboard handling, tree restoration, accessibility, and live result
  changes in a real browser
- Record server work, payload size, and DOM insertion budgets against public synthetic
  large-tree fixtures

## Rollout Plan

Ship bounded in-memory inventory search first.
Keep persistent metadata out of the initial contract and add it only after measurements
identify a concrete warm-start or capacity problem.
Search remains optional UI and does not delay the initial tree or direct-file preview.

## Open Questions

- Which focus shortcut avoids browser-reserved keys while remaining discoverable on
  macOS, Windows, and Linux?
- Which measured default result limit and debounce interval satisfy both local and
  remote roots? The starting candidates are the existing 200-row tree page and its
  current filter-reapply debounce.
- Should type-family expansion remain a browser-owned mapping or graduate to a shared
  declarative file-type table used by both Python and JavaScript?
- Do aborted maximum-inventory scans require cooperative server cancellation after
  client cancellation and off-event-loop execution are measured?
- What measurements would justify persisted metadata without making it a required
  runtime dependency?

## Acceptance Criteria

- Search never blocks the initial tree or direct-file preview
- A query cannot access or reveal a path outside the served root
- The browser shows ancestors for every returned match and preserves stable order
- Compressed artifacts match their logical file type
- Incomplete and limited results are visibly distinguishable from complete results
- File creation, rename, and removal update an active query without a full page reload
- Clearing search restores the already-mounted Files tree with its expansion and
  selection state intact
- Search refresh does not send an `all-known` inventory snapshot to the browser
- Large-root tests prove bounded server work, payload size, and DOM insertion

## References

- [Core architecture](../../../architecture.md)
- [Design system](../../../design-system.md)
- [Scanning state and recent directories](plan-2026-07-16-scanning-state-and-recent-directories.md)
- [Unified filtering](plan-2026-07-20-unified-filtering.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
