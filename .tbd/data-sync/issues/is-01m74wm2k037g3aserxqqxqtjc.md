---
type: is
id: is-01m74wm2k037g3aserxqqxqtjc
title: "PR #349 A16: build the witness MarkdownIt once; import MARKDOWN_DIFF_VERSION in _fallback"
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
created_at: 2026-11-11T08:47:03.775Z
updated_at: 2026-11-11T09:51:51.697Z
started_at: 2026-11-11T08:47:26.065Z
closed_at: 2026-11-11T09:51:51.696Z
close_reason: "A16 fixed in 04c0f235: parser built once at module level; _fallback uses MARKDOWN_DIFF_VERSION."
resolution: null
duplicate_of: null
---
Severity: Suggestion. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: markdown_projection.py:159; pull_rendered_diff.py:37-43. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
