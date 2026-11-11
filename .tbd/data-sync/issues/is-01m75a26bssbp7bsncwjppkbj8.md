---
type: is
id: is-01m75a26bssbp7bsncwjppkbj8
title: "PR #351 A3: no assertion covers age dedup, check-row structure, or muted action style"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75a1p5xdgrc0v0e1pxfpct9
hold: null
hold_until: null
created_at: 2026-11-11T12:41:57.880Z
updated_at: 2026-11-11T12:57:03.116Z
started_at: 2026-11-11T12:57:01.133Z
closed_at: 2026-11-11T12:57:03.115Z
close_reason: "fixed in 970dbbc0: checkRows and headerAges in github-pull-page-mount-behavior.js (fail on the previous page), checkActions in the pull page golden, muted/link colors in test_the_pull_request_page_carries_the_shells_primitives"
resolution: null
duplicate_of: null
---
Medium. tests/dom/github-pull-page-mount-behavior.js, tests/test_design_vocabulary.py:1399, arch-views-models-routes.md:726. Add browserless assertions on the production JS. PR #351, review A (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5855489961).
