---
type: is
id: is-01kzz03fmd769zawq6gf5d1hd7
title: "Phase 1A: Establish canonical view routes and navigation SDK"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz03fwfcvam3ft3zvfwqx7g
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
created_at: 2026-08-14T02:02:35.021Z
updated_at: 2026-08-14T02:04:47.143Z
---
Add safe direct /view/{path} shell routing, segment encoding, CLI startup URLs, legacy-hash migration, folder canonicalization, and push/replace/pop/fragment behavior in a new strict browser route module composed by app.js. Extend openPath with query and fragment options and add hrefForPath before downstream plugin work; Phase 1 adds no path-resolution endpoint. Include route, containment, history, SDK, CLI golden, and compatibility tests; run make verify.
