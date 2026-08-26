---
type: is
id: is-01m0ycshb4fbspekt6wvhbkemh
title: Default diff views to Split and order Split before Unified
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-26T06:40:47.970Z
updated_at: 2026-08-26T07:43:11.826Z
closed_at: 2026-08-26T07:43:11.825Z
close_reason: Split is first and is the fresh-session default; Unified remains second and either valid persisted choice is preserved. Exact globally installed 4d45e0d opened a fresh origin in Split and exposed the Split/Unified radiogroup in that order; focused tests and make verify pass.
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/builtin_plugins/diff/diff-view.js readLayoutPreference and renderLayoutControl; tests/dom/diff-view-behavior.js default, invalid-preference, persisted-preference, and control-order cases; docs/design-system.md diff layout control contract; docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md implementation plan; CHANGELOG.md. Behavior/invariants: a user with no stored diff.layout preference starts in split layout; Split is the left/first joined option and Unified is the right/second option; valid persisted unified or split choices remain authoritative and switch immediately without re-lexing; invalid stored values safely fall back to split; direct diff documents and revision-hosted comparisons share the same behavior. Acceptance: focused DOM tests prove option order, initial and invalid fallback, persistence, immediate reprojection, lexer reuse, and disposal; make format and make verify pass; visible-browser unified/split smoke test confirms layout and control order.
