---
type: is
id: is-01m0hj1jhk2tmycmj7rj5sjnkh
title: Filtered folder rows show unfiltered count, size, and age
kind: bug
status: closed
priority: 1
version: 3
assignee: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:02:26.610Z
updated_at: 2026-08-21T07:42:03.712Z
closed_at: 2026-08-21T07:42:03.711Z
close_reason: Folder count, size, and age now roll up from the matching leaves in the subtree; verified against the running repo (node_modules 116.5 MB to 23.9 KB under the Media preset).
---
Under an active filter, every folder row still shows the unfiltered aggregates the inventory computed for the whole directory.

Reproduced on this repository with the Media type preset (9 matching files):

- `node_modules/@highlightjs` shows 4.0 MB; its only matches are two images totalling about 19 KB.
- `node_modules/@highlightjs/cdn-assets/styles` shows 1.1 MB for the same two images.
- `docs` shows 1002.9 KB while containing no media at all.

The chip is rendered by `treeDirChipHtml(node.total_files, node.total_size)` in `renderTreeNodes` (static/app.js), from `total_files` / `total_size` / `mtime` that `_build_inventory_tree` copies off the unfiltered inventory. `applyTreeFilters` never touches them, because it is a class-toggling decoration pass over already-rendered rows.

Wanted: with a filter on, a folder's count, size, and age roll up from the matching files in its subtree. Without a filter, the numbers are unchanged.

Depends on a filtered projection that knows the whole subtree, not just the loaded rows: see the filtered tree projection bead.
