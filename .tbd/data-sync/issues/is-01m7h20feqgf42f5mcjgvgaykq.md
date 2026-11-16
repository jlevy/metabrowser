---
type: is
id: is-01m7h20feqgf42f5mcjgvgaykq
title: "PR #449 C3: with diff.submodule=diff the one run still runs a submodule own textconv and external drivers"
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
created_at: 2026-11-16T02:12:06.229Z
updated_at: 2026-11-16T02:53:22.686Z
started_at: 2026-11-16T02:53:22.348Z
closed_at: 2026-11-16T02:53:22.685Z
close_reason: C3 fixed in ae27afdce (diff.submodule=diff counts as a driver)
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914224032. References: src/metabrowser/diff/adapters/git.py:13-15, :1050-1054; src/metabrowser/diff/adapters/textconv.py:1-11, :195. See the review for the full finding and suggested fix.
