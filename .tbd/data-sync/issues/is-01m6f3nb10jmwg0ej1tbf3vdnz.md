---
type: is
id: is-01m6f3nb10jmwg0ej1tbf3vdnz
title: "Design: review PRs from a mirror or a checkout without a second copy"
kind: task
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:47.711Z
updated_at: 2026-11-02T21:47:05.392Z
started_at: 2026-11-02T21:47:05.391Z
---
Written on branch claude/v012-pr-review-design (ac340690), docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md. An overlay store borrows the checkout's objects through alternates: 5.2 s and 0 KB against 185 s and 1,240 MB for a mirror, matching GitHub on six PRs and byte-identical to the mirror's comparison. It reverses the earlier alternates rejection. Status: under independent review; the owner has not decided.
