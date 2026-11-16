---
type: is
id: is-01m7h20gbd55k1k2jf2aay1tfm
title: "PR #449 C5: a section position is not always its owner: check it and fall back to parsed owners"
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
created_at: 2026-11-16T02:12:07.148Z
updated_at: 2026-11-16T02:53:24.026Z
started_at: 2026-11-16T02:53:23.686Z
closed_at: 2026-11-16T02:53:24.025Z
close_reason: C5 fixed in 1f95b0312 (position checked by the asked headers; fallback to every header)
resolution: null
duplicate_of: null
---
Severity: suggestion. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914224032. References: src/metabrowser/diff/adapters/git.py:345, :361, :371. See the review for the full finding and suggested fix.
