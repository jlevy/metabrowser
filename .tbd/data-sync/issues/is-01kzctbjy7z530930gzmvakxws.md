---
type: is
id: is-01kzctbjy7z530930gzmvakxws
title: Gated rename and trash via POST /api/mutate with nav context-menu actions
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md
labels: []
dependencies: []
created_at: 2026-08-07T00:35:49.318Z
updated_at: 2026-08-07T00:36:02.778Z
---
Phase 2 of the menu-primitives plan. Add the --allow-edits / METAB_ALLOW_EDITS startup gate (off by default), publish a CAPABILITIES block through client_settings_dict(), and show a persistent edit-mode badge. Add mutations.py (stat-derived revision tokens, name validation, containment re-resolution immediately before acting, conflict detection, structured outcomes) and POST /api/mutate with a tagged operation union carrying rename and trash; publish successful mutations through the existing inventory event path. Wire the rename and trash actions into the registry, rename driving inline_edit.js and trash driving a confirmation on the shared modal shell. Open decision before starting: trash implementation (served-root-local quarantine dir vs send2trash, subject to the 14-day cool-off).
