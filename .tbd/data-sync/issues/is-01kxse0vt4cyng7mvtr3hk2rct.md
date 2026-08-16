---
type: is
id: is-01kxse0vt4cyng7mvtr3hk2rct
title: "Diff P1: Changes nav surface and per-file diff renderer"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-18-git-diff-view.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wddy6je24t1dm5caber
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:59.012Z
updated_at: 2026-08-16T08:06:27.290Z
extensions:
  linear:
    id: a18941f9-1b80-42ad-b5da-eaa77ec485e9
    linked_at: 2026-08-16T08:06:27.290Z
---
Third left-nav tab via repo-scoped surface mount: badge count, status list with staged/unstaged provenance, empty/non-repo/unavailable states. Strict-TS unified renderer with design tokens, selectable text, explicit binary/too-large/renamed/mode states, load-more caps. One-click diff/current/HEAD-original. Staleness from /api/events with refresh affordance.
