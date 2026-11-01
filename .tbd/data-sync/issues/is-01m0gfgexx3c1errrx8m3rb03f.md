---
type: is
id: is-01m0gfgexx3c1errrx8m3rb03f
title: Extend the views/models/routes map as surfaces are added
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T20:58:54.267Z
updated_at: 2026-11-01T16:21:25.215Z
closed_at: 2026-11-01T16:21:25.214Z
close_reason: A reminder of intent by its own description; check_parity and the docs tests now enforce the map.
resolution: canceled
duplicate_of: null
---
docs/project/architecture/arch-views-models-routes.md is the map of kinds, views, models, and routes, enforced by tests/test_views_models_routes.py and the structural conventions in tests/test_docs_discipline.py. Keep it current as surfaces land: /compare routes (mb-hgus), comparison views on changed files (mb-p2mi), archive and PR containers (mb-380k, mb-6394), and any new documented format. Registering a surface without updating the map now fails the build, so this bead is a reminder of intent rather than a gate.
