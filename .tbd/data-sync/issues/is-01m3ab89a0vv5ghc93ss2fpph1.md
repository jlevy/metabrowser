---
type: is
id: is-01m3ab89a0vv5ghc93ss2fpph1
title: "Line anchors: Markdown Source tab, ?plain=1, keyboard access, scroll on tab switch"
kind: task
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-24T18:36:10.943Z
updated_at: 2026-09-24T20:23:38.245Z
started_at: 2026-09-24T19:15:10.266Z
closed_at: 2026-09-24T20:23:38.242Z
close_reason: "PR #239: Markdown Source tab gutter/anchors, keyboard slider, first-show scroll; review fixes; CI green"
resolution: null
duplicate_of: null
---
Leftovers from line anchors (PR codex/v012-line-anchors): (1) a GitHub blob URL for a .md file with #L or ?plain=1 should open the Markdown Source tab with line anchors (the Markdown Source tab draws its own code blocks and has no line numbers yet); (2) keyboard access to line anchors (numbers are mouse-only and hidden from screen readers); (3) scroll to the anchor when an inactive Source tab of an HTML or structured file is first shown.
