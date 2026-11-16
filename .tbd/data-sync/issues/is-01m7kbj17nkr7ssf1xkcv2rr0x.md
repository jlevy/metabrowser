---
type: is
id: is-01m7kbj17nkr7ssf1xkcv2rr0x
title: "PR #489 A4: two rewrapped comments run past 100 columns"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4rbwpzbrxkf1686cpsmrm
hold: null
hold_until: null
created_at: 2026-11-16T23:37:27.540Z
updated_at: 2026-11-16T23:46:41.289Z
started_at: 2026-11-16T23:37:36.012Z
closed_at: 2026-11-16T23:46:41.287Z
close_reason: "Fixed in 9755ef12b (A4): rewrapped to 100 columns."
resolution: null
duplicate_of: null
---
Low. tests/test_design_vocabulary.py:2301 (172 columns) and builtin_plugins/diff/diff-view.js:1502 (102). Rewrap to 100. Review: https://github.com/jlevy/metabrowser/pull/489#pullrequestreview-5929864311
