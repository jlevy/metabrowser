---
type: is
id: is-01m8b7xcgmxzxrg7cnnkpfmve0
title: "Guided review: each file excerpt has the diff view's collapse chevron"
kind: feature
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T06:15:31.600Z
updated_at: 2026-11-26T07:05:16.798Z
started_at: 2026-11-26T06:15:36.371Z
---
Owner 2026-11-26: inside guided reviews, each file diff should toggle open/closed with a chevron exactly like the Changes tab's file cards, reusing the diff view's design components, not a second implementation.

## Notes

PR https://github.com/jlevy/metabrowser/pull/872 (branch claude/guide-diff-toggles), open, not merged. Both places build the bar from fileDisclosure in builtin_plugins/diff/diff-view.js: Changes' renderFileSection calls it, and mountFilePatch hands it to the guide's card as disclose on its handle. Only a card that mounts a patch folds; a card holding one sentence keeps a plain bar. Chrome check (tests/dom/github-guided-review-fold-chrome.mjs) covers a pull request's guide, not a stack's. Open question for the owner: a folded file opens again when its step is shown again, as Changes' state lasts as long as its view.
