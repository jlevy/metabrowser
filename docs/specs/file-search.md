# Scalable File Search

Status: planned after v0.1.0.

Metabrowser should provide a keyboard-first file filter without delaying first paint or
requiring the browser to materialize the complete served tree.
Search must query the existing bounded inventory and state honestly when that inventory
is incomplete.

## Goals

- Focus search with a documented keyboard shortcut that does not intercept typing in an
  input, editor, or content-editable surface.
- Match served-root-relative file paths by case-insensitive keyword.
- Filter by logical extension and modification-age window.
- Combine keyword, extension, and recency predicates predictably.
- Preserve directory hierarchy and stable child order while showing the ancestors of
  every match.
- Keep initial navigation lazy and independent of full-root search readiness.
- Report indexed counts, limits, and truncation with every result set.
- Reuse `InventoryIndex`, logical-extension handling, ignore rules, and live-event
  invalidation instead of adding a second filesystem crawl.

## Non-Goals

- Searching inside file contents.
- Blocking startup on a complete index.
- Rendering every indexed entry in the DOM.
- Requiring a database, external search daemon, or native extension for the first
  implementation.
- Hiding incomplete results when an inventory cap has been reached.

## Query Contract

The first implementation adds a bounded endpoint with semantics equivalent to:

```text
GET /api/search?q=report&ext=.md&max_age_seconds=86400&limit=500
```

Predicates combine with AND. Repeated `ext` values combine with OR. Extensions use
Metabrowser’s logical extension, so transparent compression does not create a separate
`.gz` or `.zlib` facet.

The response contains:

- matching file entries from the current inventory;
- the ancestor directories required to display those entries as a tree;
- the inventory generation used for the query;
- indexed file and directory counts;
- the configured file cap and completion or truncation state;
- a result limit and a flag indicating whether additional matches were omitted.

Paths remain served-root-relative.
The route applies the same containment and ignore policy as `/api/tree` and must not
trigger synchronous traversal on the request path.

## Browser Behavior

The search control stays outside the replaceable tree-content container so inventory
updates cannot discard focus or the current query.
Typing is debounced and cancels an obsolete request.

Results preserve their original directory hierarchy and child ordering.
Ancestors of a match expand for the search result without overwriting the user’s normal
collapsed-state preference.
Clearing the query restores the prior tree state.

An active query uses shared design tokens for a visible filtered-state indicator.
Incomplete search shows the indexed count and cap near the results; it never presents a
truncated set as exhaustive.

## Delivery Plan

1. Define and test the query and response models against a deterministic inventory.
2. Add bounded inventory queries for keyword, logical extension, and recency without
   re-statting files.
3. Add `/api/search` with validation, cancellation, stable ordering, and truncation
   metadata.
4. Add the keyboard shortcut, search control, result-tree state, and accessible empty
   and incomplete states.
5. Invalidate or refresh active results from inventory generations delivered through
   `/api/events`.
6. Measure query latency and browser rendering against synthetic roots at and beyond the
   configured inventory cap.
7. Evaluate persistent metadata only after measurements show that warm-start or larger
   roots need it.

## Acceptance

- Search never blocks the initial tree or direct-file preview.
- A query cannot access or reveal a path outside the served root.
- The browser shows ancestors for every returned match and preserves stable order.
- Compressed artifacts match their logical file type.
- Incomplete and limited results are visibly distinguishable from complete results.
- File creation, rename, and removal update an active query without a full page reload.
- Large-root tests prove bounded server work, payload size, and DOM insertion.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
