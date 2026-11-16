---
type: is
id: is-01m7h20bgysrfq5afzf8bz8p6g
title: "PR #449 B1: a page of a commit within the bound is cut from the kept patch by parsing every section header"
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
created_at: 2026-11-16T02:12:02.205Z
updated_at: 2026-11-16T02:53:17.932Z
started_at: 2026-11-16T02:53:17.586Z
closed_at: 2026-11-16T02:53:17.931Z
close_reason: B1 fixed in 1f95b0312 (positional cut, page headers only)
resolution: null
duplicate_of: null
---
Severity: Medium. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530. References: src/metabrowser/diff/adapters/git.py:983-986, :366-372, :288-319. See the review for the full finding and suggested fix.
