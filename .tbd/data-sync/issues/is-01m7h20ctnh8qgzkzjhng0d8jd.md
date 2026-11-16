---
type: is
id: is-01m7h20ctnh8qgzkzjhng0d8jd
title: "PR #449 B4: a kept textconv answer is evicted by age, not by use"
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
created_at: 2026-11-16T02:12:03.540Z
updated_at: 2026-11-16T02:53:19.985Z
started_at: 2026-11-16T02:53:19.606Z
closed_at: 2026-11-16T02:53:19.984Z
close_reason: B4 fixed in ae27afdce (kept answers evicted by use)
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530. References: src/metabrowser/diff/adapters/textconv.py:222, :266-269. See the review for the full finding and suggested fix.
