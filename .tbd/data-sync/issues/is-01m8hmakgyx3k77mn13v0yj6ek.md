---
type: is
id: is-01m8hmakgyx3k77mn13v0yj6ek
title: Prepare CLI v0.14.0 ahead of the first native app release
kind: task
status: in_progress
priority: 1
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-28T17:47:54.269Z
updated_at: 2026-11-28T17:59:00.486Z
started_at: 2026-11-28T17:58:59.663Z
---
Readiness survey at main f40a784913cd52e4244558f6ae109e4d4f11192d. Prepare the CLI changelog and exact release candidate, run the published v0.13.0 performance comparison, and verify the candidate against the complete release gate. Prioritize bounded legacy structured parsing (mb-7th1) and a Markdown worker memory ceiling (mb-zrng) before proposing a tag. Review the recurring CI timing headroom under mb-j5j2 and the owner-host watcher issue under mb-4bu6. Coordinate the native app runtime minimum and published flag with mb-1d8p. Publication follows review of the exact candidate commit and notes.

## Notes

Latest reviewed stack merged and main CI/macOS CI passed. Before tagging: resolve or explicitly triage mb-7th1 and mb-zrng, run make verify, benchmark against published 0.13.0, assemble release notes, and verify the published wheel in isolation. The native app follows after the CLI is published, using the coordinated 0.14.0 minimum.
