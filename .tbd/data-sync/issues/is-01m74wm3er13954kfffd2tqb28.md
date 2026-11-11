---
type: is
id: is-01m74wm3er13954kfffd2tqb28
title: "PR #349 B2: fenced code is highlighted at full size before any budget can reject it"
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
created_at: 2026-11-11T08:47:04.664Z
updated_at: 2026-11-11T09:51:48.265Z
started_at: 2026-11-11T08:47:22.648Z
closed_at: 2026-11-11T09:51:48.264Z
close_reason: "B2 fixed in 04c0f235: fences render without highlighting (info string kept in the hidden signature); the B2 input now projects in 5 ms. Test: test_fenced_code_is_one_text_node_without_highlighting."
resolution: null
duplicate_of: null
---
Severity: Low. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855503638. References: markdown_projection.py:162-167, 185-191. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
