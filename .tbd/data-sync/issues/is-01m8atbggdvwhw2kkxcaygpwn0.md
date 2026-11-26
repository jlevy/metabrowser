---
type: is
id: is-01m8atbggdvwhw2kkxcaygpwn0
title: "PR #860 A1: three ported Lean regexes are quadratic at the highlight limit"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-25-lean-language-support.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8atbg2cb0ctsdd9fjmkf4qb
hold: null
hold_until: null
created_at: 2026-11-26T02:18:34.381Z
updated_at: 2026-11-26T02:18:44.786Z
started_at: 2026-11-26T02:18:44.786Z
---
Severity High. src/metabrowser/static/syntax/lean.js:37,41,44: definitionBegin, keywords, interpolatedBegin scan to end of input per occurrence. Review: https://github.com/jlevy/metabrowser/pull/860#pullrequestreview-6067658886 (PR #860).
