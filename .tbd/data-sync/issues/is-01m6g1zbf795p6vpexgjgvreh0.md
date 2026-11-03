---
type: is
id: is-01m6g1zbf795p6vpexgjgvreh0
title: "PR #284 E1: the mount draws every hydrated file's rows in one task, 1.0-1.2 s at 115k nodes, so 1,031 files paint later than github.com"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6g1yw7yj073zja4jqvz0g8b
hold: null
hold_until: null
created_at: 2026-11-03T06:36:33.110Z
updated_at: 2026-11-03T07:25:43.166Z
started_at: 2026-11-03T06:36:43.635Z
closed_at: 2026-11-03T07:25:43.165Z
close_reason: "Fixed in 9b624b3a on PR #284: the mount draws the first screen and one more; later ready files are held with their answers and drawn when reached. Measured against 9d6e0930 in adjacent pairs; disposition reply https://github.com/jlevy/metabrowser/pull/284#issuecomment-6597884642"
resolution: null
duplicate_of: null
---
High. builtin_plugins/diff/diff-view.js:2362-2376 (mount loop) and renderFileSection 2226-2240: every ready file's hunks are built at mount; only deferred files use queueDeferredHydration (1869-1894). On astral-sh/ruff #29817 (1,031 files) that task is 114,609 nodes and 1,083 ms of style, layout and commit; first line 2.0-2.4 s, Back 0.9-1.3 s, Conversation click 0.9-1.3 s. Fix: draw the first screen's rows at mount and route every later ready file through the deferred path with its patch in hand. Review: https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5747841588
