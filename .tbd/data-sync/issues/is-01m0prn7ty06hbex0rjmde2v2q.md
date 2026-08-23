---
type: is
id: is-01m0prn7ty06hbex0rjmde2v2q
title: "PR #72 review R8: the _inlineTreeRows guard covers one of four non-painting returns"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:14.621Z
updated_at: 2026-08-23T07:34:14.621Z
---
app.js:842 guards on _inlineTreeRows, but renderInitialTreeRows (:808-834) also returns false without painting for rows.length===0 (truthy empty array), _lastTreeRender already set, and treeFilterKey()||filesPanelUsesRecentSource(). Each records a renderTreeNodes:inline span for a call that painted nothing, inflating tree_region_repaints — the metric the guard protects. Fix: record the span inside renderInitialTreeRows around renderFilesFromTree() at :830 and drop the call-site guard.
