---
type: is
id: is-01m7hfbebf3dph0p20h1f8zr0y
title: "PR #473 A8: compare Files section accessible names case-insensitively"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7he951v8gwjt3ejjes5d4ab
hold: null
hold_until: null
created_at: 2026-11-16T06:05:17.038Z
updated_at: 2026-11-16T06:41:00.800Z
started_at: 2026-11-16T06:05:26.542Z
closed_at: 2026-11-16T06:41:00.799Z
close_reason: "A8 fixed in 4d659021c: casefold comparison"
resolution: null
duplicate_of: null
---
Suggestion. tests/test_files_tab_chrome.py:396-403 expects label.upper(). Review A round 1 on PR #473: https://github.com/jlevy/metabrowser/pull/473#pullrequestreview-5915676394
