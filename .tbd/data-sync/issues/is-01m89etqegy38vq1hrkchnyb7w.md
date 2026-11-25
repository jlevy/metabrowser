---
type: is
id: is-01m89etqegy38vq1hrkchnyb7w
title: "PR #838 B1: when the carrier moves, Guided Review cannot read a step at the drawn comparison"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m89etpwgfvf29h3jtxjr4664
hold: null
hold_until: null
created_at: 2026-11-25T13:37:55.662Z
updated_at: 2026-11-25T13:37:59.966Z
started_at: 2026-11-25T13:37:59.965Z
---
A step not read yet is refused as a new guide, and reopening reads the re-pinned guide at the old pair as history rewritten. Fix: a step answer naming another revision while the drawn comparison is not current is that step's stack_moved; the route answers stack_moved at a kept pair the guide's pins are past; session cases.
