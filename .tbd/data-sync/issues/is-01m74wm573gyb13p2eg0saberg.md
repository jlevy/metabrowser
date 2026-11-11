---
type: is
id: is-01m74wm573gyb13p2eg0saberg
title: "PR #349 C3: every unchanged block is serialized, sent, sanitized and mounted"
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
created_at: 2026-11-11T08:47:06.465Z
updated_at: 2026-11-11T09:51:52.323Z
started_at: 2026-11-11T08:47:27.003Z
closed_at: 2026-11-11T09:51:52.322Z
close_reason: "C3 fixed in de42f53d (option b): folded runs build only when opened; 100 p90 answers mount 10,800 nodes in 110 ms against 60,100 in 188-219 ms (headless Chrome)."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855871513. References: markdown_projection.py:504-512; diff-markdown.js:145-173, 319-331. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
