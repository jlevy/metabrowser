# Feature: Scalable File Search

**Date:** 2026-07-17 (last updated 2026-07-17)

**Author:** Metabrowser maintainers

**Status:** Draft

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

Metabrowser already builds a bounded `InventoryIndex`, exposes lazy tree navigation,
normalizes logical extensions for transparently compressed files, and reports live
filesystem changes. Search should compose those contracts.
A separate crawl or complete tree copy in the browser would duplicate state, increase
startup work, and make truncation harder to report honestly.

## Design

### Approach

Add bounded query operations to `InventoryIndex` and expose them through one search
endpoint. The browser renders the matching files and their ancestors as a filtered tree
without overwriting the user’s normal navigation state.

Keyword, extension, and recency predicates combine with AND. Repeated extension values
combine with OR. Extensions use Metabrowser’s logical extension, so transparent
compression does not create separate `.gz` or `.zlib` facets.

### Components

- `InventoryIndex` evaluates keyword, logical-extension, and recency predicates without
  re-statting files
- The search route validates bounded queries and returns matches, ancestors, inventory
  state, and result-limit metadata
- Browser search state owns the query, cancellation, filtered tree, and restoration of
  the prior navigation state
- `/api/events` invalidates or refreshes active results when the inventory generation
  changes

The search control remains outside the replaceable tree-content container so inventory
updates cannot discard focus or the current query.
Typing is debounced and cancels an obsolete request.
An active query uses shared design tokens for its filtered-state and incomplete-result
indicators.

### API Changes

The first implementation adds a bounded endpoint with semantics equivalent to:

```text
GET /api/search?q=report&ext=.md&max_age_seconds=86400&limit=500
```

The response contains:

- matching file entries from the current inventory
- ancestor directories required to display the entries as a tree
- the inventory generation used for the query
- indexed file and directory counts
- the configured file cap and completion or truncation state
- a result limit and an indication that additional matches were omitted

Paths remain served-root-relative.
The route applies the same containment and ignore policy as `/api/tree` and must not
trigger synchronous traversal on the request path.

## Implementation Plan

### Phase 1: Bounded Inventory Search

- [ ] Define and test query and response models against a deterministic inventory
- [ ] Add bounded inventory queries without re-statting files
- [ ] Add `/api/search` validation, cancellation, stable ordering, and truncation
  metadata
- [ ] Add the keyboard shortcut, search control, result-tree state, and accessible empty
  and incomplete states
- [ ] Refresh active results from inventory generations delivered through `/api/events`
- [ ] Measure query latency and browser rendering at and beyond the configured inventory
  cap
- [ ] Evaluate persistent metadata only if measurements show that warm starts or larger
  roots require it

## Testing Strategy

- Unit-test predicate composition, logical extensions, limits, ordering, and inventory
  generation changes
- Test the route against traversal attempts, malformed limits, truncated inventories,
  cancellation, and concurrent filesystem changes
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

- Which default result limit and debounce interval satisfy both local and remote roots?
- Should ranking remain stable path order or add deterministic match-quality tiers?
- What measurements would justify persisted metadata without making it a required
  runtime dependency?

## Acceptance Criteria

- Search never blocks the initial tree or direct-file preview
- A query cannot access or reveal a path outside the served root
- The browser shows ancestors for every returned match and preserves stable order
- Compressed artifacts match their logical file type
- Incomplete and limited results are visibly distinguishable from complete results
- File creation, rename, and removal update an active query without a full page reload
- Large-root tests prove bounded server work, payload size, and DOM insertion

## References

- [Core architecture](../../../architecture.md)
- [Design system](../../../design-system.md)
- [Scanning state and recent directories](plan-2026-07-16-scanning-state-and-recent-directories.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
