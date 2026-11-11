---
type: is
id: is-01m74wm63gx3p43mpbqpxzjr5d
title: "PR #349 C5: the rendered route runs its own git diff per file"
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
created_at: 2026-11-11T08:47:07.375Z
updated_at: 2026-11-11T09:51:52.640Z
started_at: 2026-11-11T08:47:27.619Z
closed_at: 2026-11-11T09:51:52.639Z
close_reason: "C5 fixed in 04c0f235 and 6167e89f: one git diff hydrates up to 16 Markdown files (15.7 ms one file, 20.0 ms sixteen); test_one_git_diff_hydrates_the_markdown_files_after_the_one_asked_for."
resolution: null
duplicate_of: null
---
Severity: Low. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855871513. References: pull_rendered_diff.py:92. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
