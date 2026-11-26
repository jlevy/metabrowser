---
type: is
id: is-01m8bp7d1n0gdehmn8b4na1w9b
title: "PR #874 A1: keep absolute GitHub patch and diff URLs intact"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bp7ce37pgee1zpr3wrq5q6
hold: null
hold_until: null
created_at: 2026-11-26T10:25:39.892Z
updated_at: 2026-11-26T10:28:58.583Z
started_at: 2026-11-26T10:25:43.985Z
closed_at: 2026-11-26T10:28:58.583Z
close_reason: Round 1 of https://github.com/jlevy/metabrowser/pull/874 is being addressed by the owner's mb-b6qw (4cea6585 and later on the branch); this parallel attempt was not pushed.
resolution: duplicate
duplicate_of: is-01m8bkxf108ayt40j2hhjkrxm5
---
Review A (senior), P2, src/metabrowser/static/repository-links.js:308. A PR text linking https://github.com/<o>/<r>/pull/874.patch was rewritten as the repository file 874.patch, since the renderer had already made relative links absolute. https://github.com/jlevy/metabrowser/pull/874#pullrequestreview-6071795562
