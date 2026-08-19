---
type: is
id: is-01kxse0wddy6je24t1dm5caber
title: "Diff P2: split view, intraline, highlight enrichment, context expansion"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wpvpg9vx64phcr3bh8s
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:59.628Z
updated_at: 2026-08-19T18:29:44.101Z
extensions:
  linear:
    id: be7a39d5-c9b6-4a86-8008-0af0fff8de65
    linked_at: 2026-08-16T08:06:29.441Z
---
Split/unified toggle, whitespace toggle, bounded context expansion via content refs, intraline word spans, vendored highlight.js enrichment rendering plain text first. Adopt formal plugin event subscription and shared cache helper when available.

## Notes

Syntax highlighting split out to its own bead (diff view highlighting by layer); this bead keeps split view, intraline emphasis, and context expansion.
