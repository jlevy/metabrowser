---
type: is
id: is-01m7h20e4tb870wcytgqtckdcs
title: "PR #449 B7: _PatchBound copies every read until the patch begins"
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
created_at: 2026-11-16T02:12:04.889Z
updated_at: 2026-11-16T02:53:20.653Z
started_at: 2026-11-16T02:53:20.325Z
closed_at: 2026-11-16T02:53:20.652Z
close_reason: B7 fixed in 75d36886a (no copy per read)
resolution: null
duplicate_of: null
---
Severity: suggestion. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530. References: src/metabrowser/diff/adapters/git.py:158. See the review for the full finding and suggested fix.
