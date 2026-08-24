---
type: is
id: is-01m0tw8haj67tstjassnq9we07
title: "Step 4: Add split projection and persisted layout control"
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tz5xddw360nz6p59h5g00v
  - type: blocks
    target: is-01m0tz65wahghys5xrpbq2zk4y
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T21:54:10.385Z
updated_at: 2026-08-24T22:45:18.856Z
---
Files and functions: src/metabrowser/builtin_plugins/diff/diff-view.js functions projectUnifiedHunk, projectSplitHunk, pairChangedRun, renderSplitHunk, renderDiffToolbar, readLayoutPreference, and setLayout; tests/dom/diff-view-behavior.js. Behavior: render unified and split from the same cached line records; duplicate context with side-specific numbers/tokens; pair each contiguous changed run positionally and pad only the absent side; attach no-newline markers to their source side; render one always-visible Unified/Split radiogroup through mb.filterControls.groupHtml/bind with data-select=one and data-layout=joined; validate/persist mb.prefs diff.layout and immediately reproject the active layout. Invariants: only one projection is mounted, layout changes do not fetch or highlight, malformed preferences fall back to unified, collapsed file and expanded fold keys survive switches, and layout never auto-switches at narrow widths. TDD acceptance: cover equal/unequal replacements, pure adds/deletes, dual-context tokens, empty padding with no invented accessible text or numbers, repeated switching, restored/invalid preference, exclusive ARIA and keyboard state, and zero additional fetch/lexer calls.

## Notes

2026-08-24 task created from the focused plan. Layout is an immediate persisted in-view preference; switching reprojects cached data/tokens and never reloads, refetches, or re-highlights.
