---
type: is
id: is-01m37r4r2gttbwczyvatymwewx
title: Browser branch and tag selector for a served mirror
kind: feature
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-23T18:23:43.176Z
updated_at: 2026-09-24T18:04:54.989Z
started_at: 2026-09-24T18:04:54.988Z
---
Step 4 (codex/v012-refresh-pin) added POST /api/source/pin with {ref} or {oid} and the freshness row, but no UI to choose another branch or tag. Add a small selector in the served mirror's navigation that lists branches and tags from the mirror (bounded, with filtering), switches through the pin route, and has a browserless session plus goldens per AGENTS.md parity.
