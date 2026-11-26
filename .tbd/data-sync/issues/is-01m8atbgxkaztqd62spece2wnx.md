---
type: is
id: is-01m8atbgxkaztqd62spece2wnx
title: "PR #860 A2: ASCII \\\\b and \\\\w mis-highlight Unicode Lean identifiers"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-25-lean-language-support.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8atbg2cb0ctsdd9fjmkf4qb
hold: null
hold_until: null
created_at: 2026-11-26T02:18:34.803Z
updated_at: 2026-11-26T02:18:45.076Z
started_at: 2026-11-26T02:18:45.076Z
---
Severity Medium. lean.js:39,41,58: JavaScript word boundary is ASCII, Oniguruma is Unicode. Review: https://github.com/jlevy/metabrowser/pull/860#pullrequestreview-6067658886 (PR #860).
