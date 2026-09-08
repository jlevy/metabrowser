---
type: is
id: is-01m1z3wwmyvpm601txkkqjm0jn
title: Keep lazy and collapsed folder children current after filesystem changes
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:40:16.925Z
updated_at: 2026-09-08T00:02:45.684Z
closed_at: 2026-09-08T00:02:45.683Z
close_reason: Affected subtree cache variants and in-flight reads are invalidated, stale responses refresh before mounting, and mounted hidden children receive insertions. Regression red on original app.js and green after fix; real browser verified collapsed-folder insertion and live deletion.
resolution: null
duplicate_of: null
---
Real-browser review: prefetch d%1 while collapsed, create d%1/live%new.txt, then expand. Folder count changes to four but only three rows render; collapsing and reopening stays stale. subtreeCache is never invalidated and applyCellPatch skips insertion under a collapsed parent. Fix stale cached/in-flight subtree responses and update already-mounted hidden children without forcing lazy trees to mount.
