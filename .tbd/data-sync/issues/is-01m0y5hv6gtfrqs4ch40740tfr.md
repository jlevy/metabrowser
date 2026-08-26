---
type: is
id: is-01m0y5hv6gtfrqs4ch40740tfr
title: "Phase 4.8.1: Pin the VS Code-derived three-layer visual contract"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0y5hvk0rrcn98h6rv5d7dje
parent_id: is-01m0y5h1kk1waq5baqsvmqcx6k
created_at: 2026-08-26T04:34:15.876Z
updated_at: 2026-08-26T04:34:26.948Z
---
Files/functions:
- Update docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md with Phase 4.8 source findings, exact files/functions, invariants, tests, and acceptance.
- Update docs/project/research/research-2026-07-17-web-diff-viewer-architecture.md with the reviewed VS Code registrations.contribution.ts, diffEditor/style.css, and editorColors.ts line/text/gutter separation.
- Update docs/design-system.md with one semantic Diff Change Surfaces component contract.

Behavior/invariants:
- Three independent visual layers: pale whole-line fill, stronger refined text fill, and persistent leading gutter marker.
- CSS-only projection over existing semantic row/range classes; no new DOM or script work.
- All colors derive from --status-success/--status-error; line marker and numbers retain non-color meaning.

Acceptance:
- Documentation is zero-context, internally linked where useful, retains the common-doc footer, and make format passes.
