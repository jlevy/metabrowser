---
type: is
id: is-01m7hfbcqpjvvm5c8yw4xnd5wq
title: "PR #473 A4: no test fails if .heading-tally loses white-space: pre"
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
created_at: 2026-11-16T06:05:15.381Z
updated_at: 2026-11-16T06:40:59.685Z
started_at: 2026-11-16T06:05:25.279Z
closed_at: 2026-11-16T06:40:59.684Z
close_reason: "A4 fixed in 4d659021c: dotFromLabel measured"
resolution: null
duplicate_of: null
---
Low. tests/dom/files-tab-chrome.mjs:310-311, tests/test_files_tab_chrome.py:383, :412. Measure the dot's gap from the label. Review A round 1 on PR #473: https://github.com/jlevy/metabrowser/pull/473#pullrequestreview-5915676394
