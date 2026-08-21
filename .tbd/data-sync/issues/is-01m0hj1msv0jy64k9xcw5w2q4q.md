---
type: is
id: is-01m0hj1msv0jy64k9xcw5w2q4q
title: Filter misses matches past the 200-row page cap
kind: bug
status: closed
priority: 1
version: 3
assignee: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:02:28.922Z
updated_at: 2026-08-21T07:42:04.804Z
closed_at: 2026-08-21T07:42:04.804Z
close_reason: Presence and totals come from the index, not from mounted rows, so a match past the 200-row page cap keeps its folder.
---
`renderTreeNodes` pages children at `TREE_PAGE_SIZE` (200). `applyTreeFilters` judges a folder on the rows that are mounted, so a folder whose first page holds no match is hidden along with its `.tree-page-more` row, and the matches on later pages become unreachable.

Observed on this repository with the Media preset: `node_modules/@highlightjs/cdn-assets/styles/base16` mounts 200 of 352 children, none matching, so the folder is hidden and its "Show 152 more (352 total)" row is hidden with it. Nothing tells the reader that 152 entries were never considered.

The same cap makes the "Filtered to N files" tally a count of mounted matching rows rather than of matches: the Media preset reports 9 files in the type menu and the tally reads "Filtered to 1 file" at the root.

Wanted: the filter decides from the subtree, not from the mounted page, so a match on page 3 keeps its folder. Whatever cap remains has to be stated rather than silently applied.
