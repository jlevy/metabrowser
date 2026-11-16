---
type: is
id: is-01m7hdmjnskhcmz4bqa79kzpka
title: "PR #463 A3: paint exemptions do not name this layer's evidence"
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
created_at: 2026-11-16T05:35:19.224Z
updated_at: 2026-11-16T05:47:57.832Z
started_at: 2026-11-16T05:47:57.316Z
closed_at: 2026-11-16T05:47:57.830Z
close_reason: "Fixed in 6c0bd6f1f: the three paint exemptions name static/styles.css, tests/test_changed_file_rows_chrome.py, and the new stack-menu checks; check_parity passes."
resolution: null
duplicate_of: null
---
docs/project/architecture/arch-views-models-routes.md:992, :1001, :1003: diff.summary-paint lacks static/styles.css and the changed-file rows Chrome test; pull-files-tree-paint lacks the test; pulls-stack-groups-paint lacks the new stack-menu checks. Severity: Low. PR #463, Review A round 1: https://github.com/jlevy/metabrowser/pull/463#pullrequestreview-5915439143
