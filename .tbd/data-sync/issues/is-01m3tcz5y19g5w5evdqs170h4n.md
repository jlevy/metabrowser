---
type: is
id: is-01m3tcz5y19g5w5evdqs170h4n
title: Not-found message says Git has no credentials even when gh supplied them
kind: bug
status: in_progress
priority: 4
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T00:14:00.640Z
updated_at: 2026-10-01T00:14:26.369Z
started_at: 2026-10-01T00:14:26.367Z
---
QA record M10: not_found_or_private text says Git 'has no credentials' even when the gh credential helper answered the challenge. Reword to not claim missing credentials when a helper is configured.
