---
type: is
id: is-01m74wky768gaehzms8w8b0h9x
title: "PR #349 A5: a change inside a list, blockquote, or table repeats the whole top-level construct"
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
created_at: 2026-11-11T08:46:59.302Z
updated_at: 2026-11-11T09:51:49.821Z
started_at: 2026-11-11T08:47:24.204Z
closed_at: 2026-11-11T09:51:49.820Z
close_reason: "A5 fixed in 04c0f235 and de42f53d: item-level descent for lists and quotes, inline marks in table cells, adjacent same-kind pairs. Tests: test_list_items_change_alone_and_keep_their_numbers, test_a_quote_changes_one_paragraph_at_a_time."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: markdown_projection.py:177, 41, 290. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
