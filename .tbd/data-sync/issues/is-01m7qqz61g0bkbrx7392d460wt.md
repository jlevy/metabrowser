---
type: is
id: is-01m7qqz61g0bkbrx7392d460wt
title: "Flake: test_files_totals_stable_chrome 'ignored fast 180px light' sees a 0.00268 layout shift on #tree-content"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T16:31:19.087Z
updated_at: 2026-11-18T16:31:19.087Z
---
Main's CI at e769513d9 (run 44341818706 attempt 1, chrome 3.14 3/4, job 134941322437) failed tests/test_files_totals_stable_chrome.py:196: 'ignored fast 180px light: layout shift 0.00268' with source div#tree-content.tree-content at 91 ms. The case came with mb-h3hc (#490). It passed on the PR and on main before, so it looks timing-dependent. Find what moves #tree-content at ~91 ms in the 180px ignored case, and fix the layout, not the assertion.
