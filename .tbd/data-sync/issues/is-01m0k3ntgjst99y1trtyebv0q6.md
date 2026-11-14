---
type: is
id: is-01m0k3ntgjst99y1trtyebv0q6
title: Add diagram copy button and visible Mermaid parse-error state
kind: task
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies: []
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:50.354Z
updated_at: 2026-11-14T18:44:29.333Z
---
Phase 2 of docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md: add a copy button to the diagram figure (KPress adds none, since the figure carries kpress-diagram-source rather than kpress-code), and show a legible message when KPress sets data-kpress-diagram-status="error" and restores the source, including Mermaid's maxTextSize and maxEdges failures.
