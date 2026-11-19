---
type: is
id: is-01m0k3ntgjst99y1trtyebv0q6
title: Diagram toolbar (copy, source toggle, expand) and zoom/pan dialog
kind: task
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3ntypp20smgz56xxw8ak5
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:50.354Z
updated_at: 2026-11-19T01:37:29.301Z
---
Toolbar on hover/focus: copy source, show source or diagram, expand. Expand opens a modal dialog filling the window with zoom in/out/reset and four pan buttons (GitHub parity) plus wheel/pinch zoom about the pointer, drag pan, and keys (+ - 0 arrows Escape). The zoom/pan arithmetic is a pure state machine (viewTransform) the browserless session drives. Error state shows Mermaid's message, including maxTextSize and maxEdges refusals.
