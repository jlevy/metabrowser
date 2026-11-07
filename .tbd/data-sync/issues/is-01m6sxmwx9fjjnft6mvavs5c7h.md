---
type: is
id: is-01m6sxmwx9fjjnft6mvavs5c7h
title: Unify the left-aligned commit and PR reading headers
kind: task
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m6t02b08jdzpvf7sr2qyeb31
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T02:33:20.551Z
updated_at: 2026-11-07T03:38:21.285Z
---
Consolidate commit and PR page headers around the commit view’s left alignment and the PR view’s larger title scale. Use the existing wider rendered README reading measure as the reference for PR descriptions and comments, and align the title, metadata and tabs with the reading column. Preserve full-width comparisons. Check computed content edges and text measure in README, commit and PR views at narrow and wide pane widths.

## Notes

Implemented in 69793af1. Commit and PR titles share the left reading edge and 24px scale. PR descriptions and comments match the 662px README prose measure at default settings in checkout and managed previews. Changes remains full-width. 98 focused tests, five goldens, and independent review passed.
