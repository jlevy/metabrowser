---
type: is
id: is-01m7dqr9b4de8qgej36syy3a1s
title: "Docs: installation owns requirements; new macOS app user guide"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:08.772Z
updated_at: 2026-11-15T05:56:36.535Z
---
Phase 1, PR 3.

- docs/installation.md (about 200 lines): sole owner of install and upgrade for metab, the app, and the skill; uv, Git, and gh requirements; release-bound status stated once (today :86, :98, :107, :112, and :124 describe two release states). Keep the path stable: apps/macos ProjectLinks.swift links it.
- New docs/macos-app.md (about 150 lines): windows, tabs, recent folders, session restore, drops, settings, and choosing a metab. Sources: the user sections of apps/macos/README.md (about 9-26, 488-523, 1294-1315) and installation.md's "What the App Shows Without a Usable metab" (103-136). Delete them at their sources in this pull request.
- Add README links.
