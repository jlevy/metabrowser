---
type: is
id: is-01m7hdmk67swhm9b188svt6n0r
title: "PR #463 A4: six dead plugin classes on changed-file parts, pinned by a source test"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjqx287ha000smyytqswb
hold: null
hold_until: null
created_at: 2026-11-16T05:35:19.750Z
updated_at: 2026-11-16T05:47:59.128Z
started_at: 2026-11-16T05:47:58.665Z
closed_at: 2026-11-16T05:47:59.126Z
close_reason: "Fixed in 6c0bd6f1f: six unreferenced classes dropped; the source test asserts the shared classes only."
resolution: null
duplicate_of: null
---
diff-summary.js:303,312,318,328; pull-files-view.js:185,195; tests/test_design_vocabulary.py:2508-2521. Severity: Low. PR #463, Review A round 1: https://github.com/jlevy/metabrowser/pull/463#pullrequestreview-5915439143
