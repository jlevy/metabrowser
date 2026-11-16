---
type: is
id: is-01m7jqg69rtq31kn0f0rvswnwv
title: "PR #479 A4: a wrapped Diff summary header starts or ends a line with its dot"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7jp047k8p38s3q818n9hvc1
created_at: 2026-11-16T17:46:55.671Z
updated_at: 2026-11-16T18:32:12.224Z
closed_at: 2026-11-16T18:32:12.223Z
close_reason: "fixed in 56829857d: each dot is one item with the group before it (.diff-summary-group, inline-flex, column-gap inherit); git-commit-summary-chrome.mjs checks every width 180-400 px (and 320 px) that no line starts with a dot; the old layout failed the sweep at 256-264 px"
resolution: null
duplicate_of: null
---
Low. builtin_plugins/diff/styles.css:54-60; diff-view.js:1465-1477, :1625-1629; tests/dom/git-commit-summary-chrome.mjs:155. Review A (round 1) on PR #479: https://github.com/jlevy/metabrowser/pull/479#pullrequestreview-5924585584
