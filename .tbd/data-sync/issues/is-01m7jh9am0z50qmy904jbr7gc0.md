---
type: is
id: is-01m7jh9am0z50qmy904jbr7gc0
title: "PR #464 B2: the Chrome check's address step is flaky: stacks after the first window regroup #7 out of view"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T15:58:19.263Z
updated_at: 2026-11-16T15:58:29.333Z
started_at: 2026-11-16T15:58:29.331Z
---
Medium. Review B (follow-up, round 2) on PR #464: https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5922595963. tests/dom/nav-reveal-chrome.mjs:347-350 (step 8) and :447-451 (step 10, relaxed by d711ab1); src/metabrowser/builtin_plugins/github/pulls-panel.js:2737-2741, :2984-2988, :4075, :4305 (a paint keeps the first row in view, refreshed on every scroll, so a regroup after the reveal moves #7). Fix: confirm with a Chrome check that delays the stacks answer past the first window; keep the revealed row as the place a paint keeps until the reader scrolls; restore step 10's wait for the reveal.
