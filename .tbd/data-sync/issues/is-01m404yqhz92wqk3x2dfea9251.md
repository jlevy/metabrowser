---
type: is
id: is-01m404yqhz92wqk3x2dfea9251
title: Implement storage resolvers and separate cache/config lifecycle
kind: task
status: in_progress
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-03T05:49:23.902Z
updated_at: 2026-10-03T06:31:44.335Z
started_at: 2026-10-03T06:04:43.922Z
---

## Notes

Implemented on codex/v012-loose-ends: cache defaults to ~/.cache/metabrowser, configuration to ~/.config/metabrowser, honoring separate XDG bases and exact CLI/app-environment overrides. Removed METABROWSER_HOME and combined-home fallback/migration. Configuration is atomically created once and preserved byte-for-byte across cache recreation; nested or equal roots are rejected and private-storage enforcement retained. Regression and package verification recorded under mb-i6ze. Changes remain local pending commit/PR handoff.
