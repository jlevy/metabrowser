---
type: is
id: is-01m1cdvsvwaqt12yyy2cj2g8sx
title: "PR #90 CODE-07: The recent and activity transcripts can only ever pin empty results"
kind: bug
status: in_progress
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:52.859Z
updated_at: 2026-09-14T06:42:25.216Z
---
window=all with the pinned mtimes would give a deterministic non-empty pin; a one-shot CLI can structurally never show a non-empty active_files.
