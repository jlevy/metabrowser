---
type: is
id: is-01m7ey9gr8ayqmcgkn727ezd9h
title: capability.update sends index.complete false for a truncated index
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:39.303Z
updated_at: 2026-11-15T06:28:39.303Z
---
events_route._project_capability_change sends index.complete=coverage.complete, which is false when the index is truncated at the cap, while /api/index/progress and /api/index/meta send complete or truncated. The client's truncated branch on capability.update can never run.
