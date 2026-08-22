---
type: is
id: is-01m0nvhd0qyfs3pzdpww6210ja
title: "PR #66 review F8: inline tree builds the whole root level then truncates"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:05:20.150Z
updated_at: 2026-08-22T23:16:36.701Z
closed_at: 2026-08-22T23:16:36.699Z
close_reason: "Fixed: max_entries threaded through _build_inventory_tree into _build_inventory_subtree and applied after the sort, so the cap bounds the dict building and recursion rather than only the payload. The sort remains O(level) and the comment says so."
---
server.py:966-978. initial_tree[:_INLINE_INITIAL_TREE_ROWS] slices AFTER the build, so the cap bounds bytes not work. Index-only with no filesystem access, but a root with tens of thousands of immediate children pays all of it synchronously on the event loop per page load, and AGENTS.md asks for synchronous work on request paths to be bounded. Fix: pass the cap into the builder, or record why unbounded is acceptable.
