---
type: is
id: is-01m0y5h1kk1waq5baqsvmqcx6k
title: Diff intraline visual hierarchy and change gutters
kind: epic
status: open
priority: 2
version: 5
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
created_at: 2026-08-26T04:33:49.670Z
updated_at: 2026-08-26T04:34:16.955Z
---
Implement Phase 4.8 of the general diff rendering plan as a focused visual follow-up.

Scope and invariants:
- Mirror VS Code separation of whole-line, intraline-text, and gutter decorations using Metabrowser semantic success/error tokens.
- Keep every added/deleted line pale, make refined changed spans substantially stronger, and show a solid leading gutter bar for all changed lines.
- Reuse existing diff-line-add/diff-line-del and diff-intraline-change classes in unified and split layouts; add no DOM, per-row JavaScript, dependency, schema, compatibility layer, or loading-tier change.
- Preserve grid alignment, selectable exact text, syntax foreground ownership, >=4.5:1 syntax contrast, and non-color +/- and line-number signals.
- Reconcile the active spec, research, design system, CHANGELOG, focused tests, real-browser light/dark evidence, full verification, and stacked PR delivery.
