---
type: is
id: is-01m7h208x1k3akgpwt30y88k1q
title: "PR #449 A6: _NOT_LISTED comment says whitespace is never part of one revision"
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
created_at: 2026-11-16T02:11:59.520Z
updated_at: 2026-11-16T02:53:14.483Z
started_at: 2026-11-16T02:53:14.120Z
closed_at: 2026-11-16T02:53:14.482Z
close_reason: A6 fixed in cc90bd6c6 (whitespace names batched; reflog selectors one at a time after a wrong answer found)
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5913959566. References: src/metabrowser/diff/adapters/git.py:132-136. See the review for the full finding and suggested fix.
