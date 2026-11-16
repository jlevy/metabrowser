---
type: is
id: is-01m7jqg5c15yqqqzhj0h9y256k
title: "PR #479 A2: commit hover card contradicts the count-summary rule"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7jp047k8p38s3q818n9hvc1
created_at: 2026-11-16T17:46:54.720Z
updated_at: 2026-11-16T18:32:11.512Z
closed_at: 2026-11-16T18:32:11.511Z
close_reason: "fixed in 56829857d (+ f7a1ffd8d for the commit totals line): the commit hover card says its changes through changeSummary and countPartsHtml, '32 files changed · 4 A, 28 M · +1,921 −160', A/D/M order, bold counts in --text, letters in status ink at the line's weight, muted marks, words for a screen reader; pinned in git-panel-behavior.js and git-commit-summary-chrome.mjs (both themes)"
resolution: null
duplicate_of: null
---
Medium. docs/design-system.md:446-449, :479, :515; static/styles.css:6729-6741; static/git-panel.js:319-322. Owner decision in mb-khm6. Review A (round 1) on PR #479: https://github.com/jlevy/metabrowser/pull/479#pullrequestreview-5924585584
