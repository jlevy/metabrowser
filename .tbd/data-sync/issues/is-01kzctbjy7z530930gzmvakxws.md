---
type: is
id: is-01kzctbjy7z530930gzmvakxws
title: Gated rename and trash via POST /api/mutate with nav context-menu actions
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md
labels: []
dependencies: []
created_at: 2026-08-07T00:35:49.318Z
updated_at: 2026-08-13T03:13:20.038Z
---
Phase 2 of the menu-primitives plan. Add opt-in regular-file rename and Metabrowser quarantine trash through POST /api/mutate with containment, conflict, revision, cross-site, inventory, preview, and documentation contracts from the spec. Reuse the focused-row contract from mb-67ru and register F2/Delete through the shared shortcut registry from mb-zxi0, delegating to the same action descriptors used by the context menu.
