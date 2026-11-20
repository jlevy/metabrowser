---
type: is
id: is-01kxse0vt4cyng7mvtr3hk2rct
title: "Diff P1: Changes nav surface and per-file diff renderer"
kind: feature
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wddy6je24t1dm5caber
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:59.012Z
updated_at: 2026-11-20T19:15:57.663Z
closed_at: 2026-08-19T04:28:51.604Z
close_reason: Superseded by mb-p2mi (comparison context in the Files tree) and mb-yv0g (comparison view descriptors). The shell-mapping section resolved this from a bespoke surface into two existing-mechanism extensions.
extensions: {}
---
Reframed by the shell-mapping section of the spec: not a bespoke surface. The Files tree renders the comparison manifest as a third source beside tree and recent (the filesPanelUsesRecentSource precedent), scoped like a filter to changed files, with the full change-indicator set from the File Diff Format (renames with old path and folder moves, type changes, mode changes, binary). Comparison views are injected into changed files' view descriptors with Diff as the context default; selection flows through navigateToPath and preferredViewId. Later presentations (Before, rendered-at-revision, inline-in-rendered) are additional tabs from the same diff layout, per the view-phasing table.
