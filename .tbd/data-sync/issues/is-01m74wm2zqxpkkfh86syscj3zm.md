---
type: is
id: is-01m74wm2zqxpkkfh86syscj3zm
title: "PR #349 B1: the default Rendered view hides destination and comment changes inside a visibly edited block"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74wk8dt7weq5cmkt2hmdrjr
hold: null
hold_until: null
created_at: 2026-11-11T08:47:04.181Z
updated_at: 2026-11-11T09:51:47.952Z
started_at: 2026-11-11T08:47:22.329Z
closed_at: 2026-11-11T09:51:47.951Z
close_reason: "B1 fixed in 04c0f235 and de42f53d: per-block hidden signatures (destinations, titles, alt, comments, attribute syntax, fence info, in-block reference definitions) set block source_only with a visible note; renders-alike changes carry the projection notice. Tests: test_a_visible_edit_never_hides_what_only_the_source_shows and neighbours in tests/test_markdown_diff_projection.py."
resolution: null
duplicate_of: null
---
Severity: High. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855503638. References: markdown_projection.py:466-470, 396-402; diff-markdown.js:332-336. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
