---
type: is
id: is-01m74wkxmy1hs87zt77bmefr2y
title: "PR #349 A4: inline redlines reject insertions, deletions, appended sentences, and most phrase replacements"
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
created_at: 2026-11-11T08:46:58.717Z
updated_at: 2026-11-11T09:51:49.512Z
started_at: 2026-11-11T08:47:23.897Z
closed_at: 2026-11-11T09:51:49.511Z
close_reason: "A4 fixed in 04c0f235: bounded difflib word diff of the trimmed span, witnessed once in the contiguous changed lines. Test: test_word_edits_mark_insertions_deletions_and_phrases."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: markdown_projection.py:335-343. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
