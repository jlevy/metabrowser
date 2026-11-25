---
type: is
id: is-01m8a59htd2xnk115y8a597zbz
title: "Guidance: correct by construction; tests check invariants, not the source"
kind: task
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T20:10:30.093Z
updated_at: 2026-11-25T22:25:45.267Z
started_at: 2026-11-25T20:10:47.207Z
closed_at: 2026-11-25T22:25:45.263Z
close_reason: "Merged in stack #846 (main 1cfd383d3)"
resolution: null
duplicate_of: null
---
User rule 2026-11-25: do not write purely duplicative tests; prefer constructions that make mistakes impossible; tests check underlying invariants, not what the code already says. Recorded in docs/development.md (Correct by Construction) and AGENTS.md.
