---
type: is
id: is-01m6fpn2641ksmffg4j0vvhk0x
title: "PR #281 D3: the shell's freshness row paints Refresh refused (HTTP 429) for an ask the reader did not make"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
hold: null
hold_until: null
created_at: 2026-11-03T03:18:41.602Z
updated_at: 2026-11-03T03:50:29.623Z
started_at: 2026-11-03T03:50:29.622Z
---
Low. src/metabrowser/static/source-freshness.js:512-514, 549-551. Fix: say nothing for poll()'s own ask, read body.error on a press; plain folders unchanged. Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
