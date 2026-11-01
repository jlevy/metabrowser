---
type: is
id: is-01m3zcr2af17a3z56qgarrh5n6
title: JSONL log event rows are not keyboard-focusable and lost their clickable accessibility node
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-02T22:46:19.726Z
updated_at: 2026-11-01T16:05:49.043Z
started_at: 2026-11-01T16:05:49.042Z
---
Browser differential: 0.11.0 exposed each JSONL log header row as a clickable generic container in the accessibility tree; after inline handlers were removed (delegated controls, SDK 0.7) the stack exposes only the icon and text. Rows still respond to a pointer click. Neither build makes them keyboard-focusable. Give the rows a real control role, a tab stop and Enter/Space handling, with a browserless interaction test.
