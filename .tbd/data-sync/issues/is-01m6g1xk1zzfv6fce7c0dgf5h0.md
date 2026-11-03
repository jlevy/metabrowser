---
type: is
id: is-01m6g1xk1zzfv6fce7c0dgf5h0
title: "PR #285 C1: the Files handler's scope and the focus fallback have no test"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
created_at: 2026-11-03T06:35:35.356Z
updated_at: 2026-11-03T06:35:35.356Z
---
app.js:8105-8113 creates the Files tree keyboard handler on #tab-files and :8064-8071 takes only a [data-tree-id] row for the overlay focus fallback; mutations M3 and M4 pass every golden. Pin both in a browserless session that loads app.js. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Medium).
