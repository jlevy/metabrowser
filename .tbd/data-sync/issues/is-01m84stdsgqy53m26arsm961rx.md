---
type: is
id: is-01m84stdsgqy53m26arsm961rx
title: "Rendered diff: show a file with raw HTML, sanitized as the document view does"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-23T18:13:47.945Z
updated_at: 2026-11-23T18:52:56.373Z
started_at: 2026-11-23T18:52:56.371Z
---
markdown_projection.py refuses any file with raw HTML (raw_html). Render it through the same sanitizer the Markdown document view uses, and match changes by the raw source in the block's signature.
