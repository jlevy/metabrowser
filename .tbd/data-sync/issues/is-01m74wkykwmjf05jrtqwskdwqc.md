---
type: is
id: is-01m74wkykwmjf05jrtqwskdwqc
title: "PR #349 A6: most bounds have no recorded measurement; node budget checked after both parses"
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
created_at: 2026-11-11T08:46:59.707Z
updated_at: 2026-11-11T09:51:50.132Z
started_at: 2026-11-11T08:47:24.519Z
closed_at: 2026-11-11T09:51:50.131Z
close_reason: "A6 fixed in 04c0f235 and 6167e89f: each constant records its measurement; element and node budgets stop the second render; line and code-block limits removed as unmeasured costs. Contract tests for tokens, nesting, nodes, code blocks, inline words, HTML cap."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: markdown_projection.py:27-37, 452-454; pull_rendered_diff.py:112, 148-150. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
