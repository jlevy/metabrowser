---
type: is
id: is-01m8cqaes3exyw92wmaqqcr83n
title: Show the actual checkout path with standard path tooltip styling
kind: feature
status: closed
priority: 2
version: 4
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cq5rvmb8jvrvqtqba4r980
child_order_hints:
  - is-01m8ct2cq59gct2eh74hsy4y8j
hold: null
hold_until: null
created_at: 2026-11-26T20:04:02.674Z
updated_at: 2026-11-26T21:05:12.421Z
started_at: 2026-11-26T20:04:21.417Z
closed_at: 2026-11-26T21:05:12.415Z
close_reason: "Implemented and independently reviewed in merged Metabrowser PR #892. Exact-head CI passed."
resolution: null
duplicate_of: null
---
Use the resolved working-tree directory and the existing design-system tooltip treatment for paths. For cloud sources identify the remote and sync state without exposing the local cache path.
