---
type: is
id: is-01m74wm3vtsphtfq4pp4fwnm38
title: "PR #349 B3: no test runs the client sanitizer path or the hostile corpus through the new code"
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
created_at: 2026-11-11T08:47:05.081Z
updated_at: 2026-11-11T09:51:48.574Z
started_at: 2026-11-11T08:47:22.962Z
closed_at: 2026-11-11T09:51:48.573Z
close_reason: "B3 fixed in 04c0f235 and de42f53d: hostile corpus through project_markdown_diff (test_hostile_markdown_projects_only_allowlisted_snapshot_markup) and a browserless session running the production sanitizeBlock and inert-html.js (tests/dom/diff-markdown-sanitize-session.js), mutation-checked."
resolution: null
duplicate_of: null
---
Severity: Low. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855503638. References: tests/dom/diff-markdown-behavior.js:68-70, 152-153; diff-markdown.js:108-136. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
