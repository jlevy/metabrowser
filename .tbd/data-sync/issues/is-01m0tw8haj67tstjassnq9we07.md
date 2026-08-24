---
type: is
id: is-01m0tw8haj67tstjassnq9we07
title: "Diff view: implement unified and split projections"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies: []
parent_id: is-01kxse0wddy6je24t1dm5caber
created_at: 2026-08-24T21:54:10.385Z
updated_at: 2026-08-24T21:58:03.955Z
---
Implement the focused plan's Phase 2 over the shared highlighted line model: positional old/new changed-run pairing, an immediate Unified/Split control backed by diff.layout, one mounted projection, and state preservation across switches. This task is the split-layout slice of mb-hhmb; intraline emphasis, whitespace controls, and context expansion remain on the parent feature.

## Notes

2026-08-24 task created from the focused plan. Layout is an immediate persisted in-view preference; switching reprojects cached data/tokens and never reloads, refetches, or re-highlights.
