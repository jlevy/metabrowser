---
type: is
id: is-01kzymejqwq8z5avxtpmcjgcac
title: Resolve blank Files overview after live directory changes
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - browser
  - folder-overview
  - regression
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T22:38:55.739Z
updated_at: 2026-08-13T22:56:07.599Z
closed_at: 2026-08-13T22:56:07.589Z
close_reason: "Implemented and verified in f2ea147: live watcher reconciliation keeps rebuilt directories indexed, completed misses are terminal, and non-extension breakdown rows use the generic file icon."
---
The dist/ directory can render as two persistent skeleton lines instead of a completed Files overview after build artifacts are created while Metabrowser is running. Reproduce from the live app, identify the rollup or state-transition cause, and ensure completed, empty, and generated-artifact directories render an explicit stable result.
