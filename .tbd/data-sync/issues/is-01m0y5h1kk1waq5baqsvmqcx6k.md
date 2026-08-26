---
type: is
id: is-01m0y5h1kk1waq5baqsvmqcx6k
title: Diff intraline visual hierarchy and change gutters
kind: epic
status: closed
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies: []
parent_id: is-01kxse0wddy6je24t1dm5caber
child_order_hints:
  - is-01m0y5hv6gtfrqs4ch40740tfr
  - is-01m0y5hvk0rrcn98h6rv5d7dje
  - is-01m0y5hvxah44e9kdbnmpq97hs
  - is-01m0y5hw7w8fdw9herhmph9qqs
  - is-01m0ycs63s5tm53hqjw2xraw1m
created_at: 2026-08-26T04:33:49.670Z
updated_at: 2026-08-26T07:43:12.426Z
closed_at: 2026-08-26T07:43:12.424Z
close_reason: "The reopened visual-correction scope is complete through mb-l00d: pure lines use strong fills, refined unchanged portions use pale fills, changed spans restore strong emphasis, and every changed line keeps a semantic gutter bar. The design-system contract, tests, exact installed browser evidence, and make verify are complete."
resolution: null
duplicate_of: null
---
Implement Phase 4.8 of the general diff rendering plan as a focused visual follow-up.

Scope and invariants:
- Mirror VS Code separation of whole-line, intraline-text, and gutter decorations using Metabrowser semantic success/error tokens.
- Keep every added/deleted line pale, make refined changed spans substantially stronger, and show a solid leading gutter bar for all changed lines.
- Reuse existing diff-line-add/diff-line-del and diff-intraline-change classes in unified and split layouts; add no DOM, per-row JavaScript, dependency, schema, compatibility layer, or loading-tier change.
- Preserve grid alignment, selectable exact text, syntax foreground ownership, >=4.5:1 syntax contrast, and non-color +/- and line-number signals.
- Reconcile the active spec, research, design system, CHANGELOG, focused tests, real-browser light/dark evidence, full verification, and stacked PR delivery.

## Notes

Reopened: Follow-up visual correction: pure added/deleted rows must use the stronger fill, while only intraline-refined rows use a pale unchanged-area fill with stronger changed spans.
