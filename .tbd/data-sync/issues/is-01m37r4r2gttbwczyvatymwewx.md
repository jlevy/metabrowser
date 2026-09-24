---
type: is
id: is-01m37r4r2gttbwczyvatymwewx
title: Browser branch and tag selector for a served mirror
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-23T18:23:43.176Z
updated_at: 2026-09-24T19:08:23.036Z
started_at: 2026-09-24T18:04:54.988Z
closed_at: 2026-09-24T19:08:23.032Z
close_reason: "Branch and tag selector: PR #236 (codex/v012-ref-selector, head 05875cd4, above #234). GET /api/source/refs, keep-the-page switching through /api/source/pin view to view_href, and an accessible selector. Independent review; all findings fixed. CI green on all nine checks."
resolution: null
duplicate_of: null
---
Step 4 (codex/v012-refresh-pin) added POST /api/source/pin with {ref} or {oid} and the freshness row, but no UI to choose another branch or tag. Add a small selector in the served mirror's navigation that lists branches and tags from the mirror (bounded, with filtering), switches through the pin route, and has a browserless session plus goldens per AGENTS.md parity.
