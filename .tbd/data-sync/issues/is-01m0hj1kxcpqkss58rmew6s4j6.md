---
type: is
id: is-01m0hj1kxcpqkss58rmew6s4j6
title: Expanding a filtered folder deletes it, selection included
kind: bug
status: closed
priority: 0
version: 4
assignee: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:02:28.011Z
updated_at: 2026-08-21T07:42:26.675Z
closed_at: 2026-08-21T07:42:04.259Z
close_reason: Rows are pruned before they are drawn, so expanding never removes the row that was clicked. The separate case of navigating to an excluded folder is now mb-h5oq.
---
Expanding a folder under an active filter can delete it from the tree, including the folder you just navigated into.

Reproduced with the Media preset on this repository:

1. Click `devtools`. It expands and shows `__pycache__`.
2. Click `__pycache__`. Both rows vanish. The main pane still shows `devtools/__pycache__` and the breadcrumb still reads it, but the nav panel no longer contains either row, and nothing is selected.
3. Same for `src/metabrowser/builtin_plugins/agent_log`, and for `node_modules/@highlightjs/cdn-assets/es`.

This is the visible consequence of the empty-folder bead: the row was only being kept because its subtree was unloaded, so loading it is what proves it should never have been shown. `loadSubtree` calls `applyTreeFilters()` on the freshly rendered children, that verdict propagates up, and the folder hides itself.

Two things are wrong even once folders are pruned up front:
- The selected row must never be filtered away. Whatever the main pane is showing has to stay visible and selected in the nav, the way a breadcrumb does.
- A row must not disappear under the pointer as a direct result of the click that opened it.

## Notes

Correction: the follow-up bead for navigating to a folder the filter excludes is [[mb-gx7s]], not the id named in the close reason.
