---
type: is
id: is-01m74wkx77k0wgjygbne47qezj
title: "PR #349 A3: rewrap or whitespace-only edits show as removed and added blocks without a note"
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
created_at: 2026-11-11T08:46:58.279Z
updated_at: 2026-11-11T09:51:49.195Z
started_at: 2026-11-11T08:47:23.581Z
closed_at: 2026-11-11T09:51:49.194Z
close_reason: "A3 fixed in 04c0f235: whitespace-collapsed render comparison shows rewraps, trailing spaces and renumbering as context under the notice. Test: test_source_changes_that_render_alike_show_as_unchanged_with_the_notice."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: markdown_projection.py:466-471. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
