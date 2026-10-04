---
type: is
id: is-01m404yqhz92wqk3x2dfea9251
title: Implement storage resolvers and separate cache/config lifecycle
kind: task
status: closed
priority: 2
version: 5
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-03T05:49:23.902Z
updated_at: 2026-10-04T22:11:18.208Z
started_at: 2026-10-03T06:04:43.922Z
closed_at: 2026-10-04T22:11:18.208Z
close_reason: Design and implementation completed in cbb92dc9, draft PR https://github.com/jlevy/metabrowser/pull/268. Local 4005 tests and 278 golden checks passed; all GitHub Python/Git/distribution checks passed. Remaining dependency audit and manual release acceptance are tracked separately under mb-19fc, mb-i6ze, and the release stability epic.
resolution: null
duplicate_of: null
---

## Notes

Implemented in commit cbb92dc9: cache defaults to ~/.cache/metabrowser, configuration to ~/.config/metabrowser, honoring separate XDG bases and exact CLI/app-environment overrides. Removed METABROWSER_HOME and combined-home fallback/migration. Configuration is atomically created once and preserved byte-for-byte across cache recreation; nested or equal roots are rejected and private-storage enforcement retained. Regression and package verification recorded under mb-i6ze. User approved push and draft PR; installed local candidate is 0.11.1.dev669+cbb92dc9.
