---
type: is
id: is-01kzz4dw3cv7ct4fm76xxw9n9r
title: "Obsidian B: Build deterministic note lookup and ambiguity handling"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dwh6esscmk8twen8dydt
  - type: blocks
    target: is-01kzz4dwwjgch14nr5rhh2j1vm
parent_id: is-01kzz03gcp4q0qfw350d6krs7q
created_at: 2026-08-14T03:18:09.772Z
updated_at: 2026-08-14T03:18:10.577Z
---
Build a bounded completion-aware inventory index for Obsidian note lookup only. Apply exact relative and vault-path precedence, optional .md for notes, required extensions for non-Markdown attachments, exact source-directory preference, and unique basename or path-suffix fallback. Return pending while inventory is incomplete, retain all candidates when ambiguous, never choose by inventory order, and re-enhance only the current mount. Add index, ambiguity, bounds, and disposal tests.
