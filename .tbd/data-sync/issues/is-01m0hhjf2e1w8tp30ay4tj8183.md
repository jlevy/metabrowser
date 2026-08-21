---
type: is
id: is-01m0hhjf2e1w8tp30ay4tj8183
title: "Nav panel filtering: correct rollups, no empty folders, stable expansion, full-width rows"
kind: epic
status: open
priority: 1
version: 13
labels: []
dependencies: []
child_order_hints:
  - is-01m0hj1jhk2tmycmj7rj5sjnkh
  - is-01m0hj1jwpjnza3gfn4tjvab1d
  - is-01m0hj1kxcpqkss58rmew6s4j6
  - is-01m0hj1mb77mk6t2440pn6pp5j
  - is-01m0hj1msv0jy64k9xcw5w2q4q
  - is-01m0hj1n6r1sqrabjrxat3a6xp
  - is-01m0hj5aes8c5kwcp0f7gpmnje
  - is-01m0hj5ass469axrp70tta93j9
  - is-01m0hj5b44s8vt9sap50651tzr
  - is-01m0hma35277yxv02a4ac0dq7d
created_at: 2026-08-21T06:54:11.533Z
updated_at: 2026-08-21T07:49:37.096Z
extensions:
  linear:
    id: e89638bb-383b-4fef-882b-93118c6efc17
    linked_at: 2026-08-21T07:05:39.735Z
---
Filtering and the navigation tree disagree once a filter is on. Reported from running Metabrowser on this repository, pulling out the nav panel, and filtering to a narrow type set (for example media files).

Symptoms to fix:

1. Folder chips still show unfiltered aggregates. Under a filter, a folder's file count, total size, and age should roll up from the files that survive the filter, not from the whole directory.
2. Empty folders are listed. Folders whose entire subtree is filtered out still appear; they should never have been listed.
3. Expanding a filtered folder makes it vanish. Expand a kept folder, its children load, nothing matches, and the row disappears under the cursor.
4. Expansion can wedge. After some rows disappear, further expand clicks stop responding.
5. Selection box is inset by nesting depth. In the nav panel the selection and hover box narrows and shifts right for nested rows. It should always span the full width of the panel, with indentation inside the row.

Root cause hypothesis: filtering is a DOM decoration layer (applyTreeFilters in static/app.js) over rows the server already rendered from unfiltered inventory. It can only judge what is loaded, so a collapsed or lazily stubbed folder is unknown and kept, and aggregates come from the unfiltered index. The fix likely needs a server-side filtered projection (the /api/filter/tree work named in mb-tyvd phase 2) plus filtered rollups, so folder presence and folder totals are both answered before render.

Also in scope: make this logic testable from the CLI (headless DOM behavior tests and CLI goldens) instead of requiring browser-based visual checks.

## Notes

Landed on branch claude/nav-panel-filtering-bugs-a55071.

Five of the six reported problems are fixed and closed: filtered rollups (mb-rz7v), empty folders (mb-pv64), vanishing rows (mb-y9if), unresponsive expansion (mb-2sc1), the 200-row page cap (mb-1lx3), and full-width rows (mb-m25i). The projection that carries the first five is mb-np5r; CLI testability is mb-21og.

Shape of the fix: the filter moved from a DOM decoration pass to a server projection. metabrowser/tree_filter.py rolls up matching leaves per directory in one pass over the index, memoized against the inventory generation so one filter change costs one pass rather than one per request the prefetch sweep fans out into. /api/tree takes types, recency, min_size, and include_ignored, and returns the pruned tree with filtered aggregates plus a filtered totals block. The browser still classifies leaves that arrive on /api/events, and deliberately does not refetch on filesystem bursts: repainting would collapse the tree under a reader.

Testability: metab --walk gained the same filter vocabulary in every output format, with a golden at tests/golden/cli-walk-filter.tryscript.md; metab --check-api gained a filtered step; tests/test_tree_filter.py covers the projection directly.

Left open: mb-gx7s (a filtered tree has no row for the folder you are standing in) and mb-5y86 (extract the remaining client-side filter decision into a headless-testable module).
