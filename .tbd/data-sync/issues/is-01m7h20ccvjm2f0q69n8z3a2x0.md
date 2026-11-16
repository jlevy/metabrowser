---
type: is
id: is-01m7h20ccvjm2f0q69n8z3a2x0
title: "PR #449 B3: MAX_LISTED_PATCH_BYTES record does not say why 256 KiB"
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
created_at: 2026-11-16T02:12:03.098Z
updated_at: 2026-11-16T02:53:19.262Z
started_at: 2026-11-16T02:53:18.927Z
closed_at: 2026-11-16T02:53:19.261Z
close_reason: B3 fixed in 12167dfe3 (docstring states the trade); sweep tracked as mb-foi8
resolution: null
duplicate_of: null
---
Severity: Low. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530. References: src/metabrowser/diff/adapters/git.py:100-109. See the review for the full finding and suggested fix.
