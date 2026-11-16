---
type: is
id: is-01m7jqg6s7qnhxs6nncw9mtxye
title: "PR #479 A5: Checks summary hides its dots with nothing said in words"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7jp047k8p38s3q818n9hvc1
created_at: 2026-11-16T17:46:56.166Z
updated_at: 2026-11-16T18:32:12.576Z
closed_at: 2026-11-16T18:32:12.575Z
close_reason: "fixed in 56829857d (+ f7a1ffd8d): separator parts carry spoken ', ' rendered in .visually-hidden on lines without a name: the Checks summary, the Diff summary's no-files and fallback lines, and the commit totals line; pinned in count-parts-session.js, diff-view-behavior.js, github-pull-core-preview-behavior.js, git-panel-behavior.js"
resolution: null
duplicate_of: null
---
Low. builtin_plugins/github/pull-page.js:5329-5333. Review A (round 1) on PR #479: https://github.com/jlevy/metabrowser/pull/479#pullrequestreview-5924585584
