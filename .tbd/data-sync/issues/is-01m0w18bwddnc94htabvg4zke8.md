---
type: is
id: is-01m0w18bwddnc94htabvg4zke8
title: Implement VS Code-derived intraline diff refinement
kind: epic
status: open
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies: []
parent_id: is-01kxse0wddy6je24t1dm5caber
child_order_hints:
  - is-01m0w195sn8t0ngjst2v899n93
  - is-01m0w1963rb0f4ph8bcz8q74se
  - is-01m0w19hbfg4xtvqy57007wncf
  - is-01m0w19z4e4ze02hwv6m24zvqv
  - is-01m0w1a9mspr5zknta7jg40j3n
  - is-01m0w1ane5z1tkemm258pkpq60
  - is-01m0w1b43a6zy5a3j7z4yv76v7
  - is-01m0w1bh84kq4t17bjwxyqv5mj
created_at: 2026-08-25T08:40:42.124Z
updated_at: 2026-08-25T08:42:25.923Z
---
Implement Phase 4 of the active general diff rendering plan as one focused browser-only refinement slice.

Scope and invariants:
- Port only the pinned VS Code character-diff primitives needed for changed-run refinement; no editor model, move detection, dependency, worker, or wire-schema change.
- Derive monotonic old/new rows and UTF-16-safe intraline spans from the existing semantic line model.
- Render unified and split layouts from one cached model, compose syntax and intraline layers without innerHTML, and preserve exact selectable text.
- Keep syntax and intraline independently optional with progressive, abortable, disposal-safe enhancement.
- Use measured browser evidence for any separate work bound; otherwise rely on the existing patch/hydration boundary and honest whole-line fallback.
- Deliver token-based light/dark/high-contrast visuals, focused and real-browser tests, attribution, architecture/research/spec reconciliation, CHANGELOG, full verification, and PR #81 exact-head CI.

This epic is a child of mb-hhmb so completion closes only Phase 4; context expansion, whitespace controls, and virtualization/worker evaluation remain open in the parent.
