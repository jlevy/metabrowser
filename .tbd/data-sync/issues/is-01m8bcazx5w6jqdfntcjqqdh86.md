---
type: is
id: is-01m8bcazx5w6jqdfntcjqqdh86
title: "Guided review: a folded file stays folded across steps, tab switches and polls"
kind: task
status: in_progress
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T07:32:51.747Z
updated_at: 2026-11-26T08:36:04.339Z
started_at: 2026-11-26T08:20:30.143Z
---
Review A of #872, A6: a folded file reopens on Next then Back, on returning to the tab, and on a poll reporting a moved head. If folds should last the guide's life, keep them in the mounted guide keyed by step and path. Owner's call.

## Notes

Done in PR https://github.com/jlevy/metabrowser/pull/872 (branch claude/guide-diff-toggles), open, not merged. A file folded in a guided review stays folded across Next and Back, a return to the tab, and a poll that draws the step again, and the folds are dropped when the guide is read at a new head. Kept for the document beside the step answers (folds in builtin_plugins/github/guide-reads.js, cleared by guideReads.clear), keyed by step, place in the step, and path; not in the mounted guide, because the guide is mounted again each time its tab is drawn and folds kept there would not survive the tab. Not covered: a file a step cites whole, which is the diff view's own card. Covered by tests/dom/github-guided-review-mount-behavior.js and tests/golden/cli-ui-github-guided-review.tryscript.md; no Chrome test.
