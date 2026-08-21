---
type: is
id: is-01m0hj5aes8c5kwcp0f7gpmnje
title: "Filtered tree projection on /api/tree: prune empty subtrees, roll up matches"
kind: feature
status: open
priority: 0
version: 1
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:04:29.400Z
updated_at: 2026-08-21T07:04:29.400Z
---
The nav filter is applied in the browser as a class-toggling pass over rows that are already mounted (`applyTreeFilters` in static/app.js). That layer cannot answer the two questions the filter actually raises, because it does not have the data:

- Does this subtree contain a match? Only loaded rows can be judged, so every collapsed folder and every lazy stub is kept as "unknown".
- What do the matches in this subtree add up to? The chips carry the unfiltered inventory aggregates.

The client cannot fix this on its own. `/api/stream` is scoped to `root-depth-2`, so the browser's FileStore holds no entries at depth 3 or deeper.

The server does have the whole index in memory. `_build_inventory_tree` (metabrowser/tree.py) already does a single parent-to-children pass over `inv.entries(scope="all-known")`, which is the same pass a filtered rollup needs.

Plan: accept the filter on `/api/tree` (types, recency, min size, include_ignored), matching the vocabulary in static/filter_state.js, and return a tree in which

- a directory appears only if its subtree contains at least one matching file,
- `total_files`, `total_size`, and `mtime` on a directory are the rollup of the matching files in its subtree,
- files appear only if they match,
- the envelope carries the true total number of matches so the tally is not a count of mounted rows.

Deliberately on `/api/tree` rather than a separate `/api/filter/tree`: the shape is the same tree, and lazy expansion, paging, and prefetch should keep running through one path rather than forking by mode. `/api/*` is an internal contract (see AGENTS.md), so the route, the client, and CHANGELOG.md change together.

Fixes the filtered-rollup, empty-folder, vanishing-row, and page-cap beads.
