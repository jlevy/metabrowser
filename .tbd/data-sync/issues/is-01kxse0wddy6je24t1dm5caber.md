---
type: is
id: is-01kxse0wddy6je24t1dm5caber
title: "Diff P2: intraline, context expansion, whitespace, and virtualization"
kind: feature
status: open
priority: 2
version: 13
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wpvpg9vx64phcr3bh8s
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
child_order_hints:
  - is-01m0tw8haj67tstjassnq9we07
  - is-01m0w062fn61tjrdp37vnga45p
created_at: 2026-07-18T01:38:59.628Z
updated_at: 2026-08-25T08:37:19.136Z
extensions:
  linear:
    id: be7a39d5-c9b6-4a86-8008-0af0fff8de65
    linked_at: 2026-08-16T08:06:29.441Z
---
Intraline word/character refinement, bounded context expansion through content references, whitespace controls, and measured virtualization or worker evaluation. Phase 4 of docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md now specifies the intraline slice as a focused VS Code-derived browser algorithm over the existing semantic line model; unified/split layout and bounded Highlight.js enrichment remain complete.

## Notes

Unified/split layout and syntax highlighting completed by mb-sj1s. The 2026-08-25 Phase 4 addendum chooses a pinned, attributed port of VS Code's pure DP/Myers refinement and boundary heuristics, with browser-local ranges, monotonic split pairing, lighter similar-line tints, stronger changed-range tints, exact-text/syntax composition, measured bounds, and whole-line fallback. Planning evidence is closed in mb-vlz2 and published in PR #81 at commit efa6c97 with exact-head CI green. Context expansion, whitespace controls, and virtualization/worker evaluation remain separate follow-up scope. PR #76 finding 76-6 continues to defer any hunk-boundary lexical-confidence cue until full-source tokenization or context expansion can replace the per-hunk reset honestly.
