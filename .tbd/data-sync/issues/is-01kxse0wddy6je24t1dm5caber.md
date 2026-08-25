---
type: is
id: is-01kxse0wddy6je24t1dm5caber
title: "Diff P2: intraline, context expansion, whitespace, and virtualization"
kind: feature
status: open
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wpvpg9vx64phcr3bh8s
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
child_order_hints:
  - is-01m0tw8haj67tstjassnq9we07
created_at: 2026-07-18T01:38:59.628Z
updated_at: 2026-08-25T07:29:06.778Z
extensions:
  linear:
    id: be7a39d5-c9b6-4a86-8008-0af0fff8de65
    linked_at: 2026-08-16T08:06:29.441Z
---
Intraline word spans, bounded context expansion through content references, whitespace controls, and measured virtualization or worker evaluation. Unified/split layout and bounded Highlight.js enrichment are complete in docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md; preserve that semantic line-model seam rather than reopening the shipped slice.

## Notes

Unified/split layout and syntax highlighting completed by mb-sj1s. Remaining scope is intraline emphasis, context expansion, whitespace controls, and virtualization/worker evaluation. PR #76 review finding 76-6 also records the accepted hunk-boundary lexical-confidence limitation: defer any reader cue until full-source tokenization or context expansion can replace the per-hunk reset honestly.
