---
type: is
id: is-01kyj6f86h79jq9gc98j9ey1ht
title: Redesign Treemap as a recursive spatial scene
kind: feature
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-07-27T16:28:02.640Z
updated_at: 2026-07-27T16:50:03.709Z
closed_at: 2026-07-27T16:50:03.701Z
close_reason: Implemented a stable recursive world plus camera projection, viewport/LOD culling, exact spatial route transitions, progressive detail refinement, persisted depth control, regression tests, spec/research updates, live browser validation, and a passing make verify gate.
---
Replace fixed one-level nesting and whole-viewport scale fades with geometry-bounded recursive rendering to an explicit depth and path-keyed spatial transitions that work at intermediate roots. Fetch enough bounded rollup depth, expose a persisted depth control, preserve route/history authority and reduced-motion behavior, add layout/renderer regression tests, update the feature spec, live-validate, run make verify, commit, push, update PR #13, and watch CI.
