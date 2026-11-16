---
type: is
id: is-01m7k4et2d6n1m5ma3wxr3jd7p
title: "PR #481 A4: the scoped hide is tested only for the folder totals"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hdc0y0089a7fe07b2y7v6v
hold: null
hold_until: null
created_at: 2026-11-16T21:33:21.868Z
updated_at: 2026-11-16T22:25:13.417Z
started_at: 2026-11-16T21:33:29.317Z
closed_at: 2026-11-16T22:25:13.416Z
close_reason: "Fixed in 04dd343f4: git-panel and treemap mocks record within; Commits checks assert #tab-git, treemap disposals assert their container (folder-plugin-behavior gains a MetabrowserTooltip observer); each fails with its call reverted to a bare hide(). Dispositions: https://github.com/jlevy/metabrowser/pull/481#issuecomment-6931212114"
resolution: null
duplicate_of: null
---
Low. PR #481 review A (https://github.com/jlevy/metabrowser/pull/481#pullrequestreview-5928039255). tests/dom/git-panel-behavior.js:560-565, tests/dom/treemap-not-indexed-session.js:48, tests/dom/folder-plugin-behavior.js (no MetabrowserTooltip). Reverting git-panel.js:2252 or treemap.js:273/639 to a bare hide() fails nothing. Fix: record within in the mocks and assert the #tab-git stand-in and the view's container.
