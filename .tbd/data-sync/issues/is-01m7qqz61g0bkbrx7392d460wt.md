---
type: is
id: is-01m7qqz61g0bkbrx7392d460wt
title: "Flake: test_files_totals_stable_chrome 'ignored fast 180px light' sees a 0.00268 layout shift on #tree-content"
kind: bug
status: closed
priority: 1
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/563
    at: 2026-11-20T17:01:11.893Z
labels:
  - linear
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-18T16:31:19.087Z
updated_at: 2026-11-20T19:13:00.303Z
closed_at: 2026-11-18T19:55:30.214Z
close_reason: "Fixed by #563 (merged eb6e2e62f): the tree's first paint waits for the filter bar, bounded to 1 s."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 76a4a2ee-37c9-4a75-a41a-712f54b31653
    linked_at: 2026-11-20T18:00:55.608Z
---
Main's CI at e769513d9 (run 44341818706 attempt 1, chrome 3.14 3/4, job 134941322437) failed tests/test_files_totals_stable_chrome.py:196: 'ignored fast 180px light: layout shift 0.00268' with source div#tree-content.tree-content at 91 ms. The case came with mb-h3hc (#490). It passed on the PR and on main before, so it looks timing-dependent. Find what moves #tree-content at ~91 ms in the 180px ignored case, and fix the layout, not the assertion.
