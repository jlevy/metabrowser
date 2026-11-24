---
type: is
id: is-01m87byqxtqaq9bayypy2bccx0
title: "PR #771 A2: a tick plus a word edit in one item loses its word marks"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
hold: null
hold_until: null
created_at: 2026-11-24T18:09:12.629Z
updated_at: 2026-11-24T18:30:12.021Z
started_at: 2026-11-24T18:14:03.344Z
closed_at: 2026-11-24T18:30:12.016Z
close_reason: "Fixed in 1f6cb05a3 (option a): _inline_change compares an input pair ignoring checked, so the one changed text beside a tick is marked and each side keeps its own box. Confirmed by test_a_tick_beside_a_word_edit_keeps_the_words_marked (both cases fail before, pass after)."
resolution: null
duplicate_of: null
---
Low. src/metabrowser/diff/markdown_projection.py:1554-1595 (_inline_change): an input pair differing only in checked fails the equal-attributes test, so the item is drawn removed and added without word marks. PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
