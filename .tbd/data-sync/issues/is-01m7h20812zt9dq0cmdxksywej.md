---
type: is
id: is-01m7h20812zt9dq0cmdxksywej
title: "PR #449 A4: a timed-out batched rev-parse is run again one name at a time, doubling the wait"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h1z1rnzfafwf740k7yrzdh
hold: null
hold_until: null
created_at: 2026-11-16T02:11:58.625Z
updated_at: 2026-11-16T02:53:12.933Z
started_at: 2026-11-16T02:53:12.579Z
closed_at: 2026-11-16T02:53:12.932Z
close_reason: A4 fixed in 9d7578df6 (a timed-out batched rev-parse is the refusal); base behaviour tracked as mb-q9jg
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5913959566. References: src/metabrowser/diff/adapters/git.py:471-489, :503-528. See the review for the full finding and suggested fix.
