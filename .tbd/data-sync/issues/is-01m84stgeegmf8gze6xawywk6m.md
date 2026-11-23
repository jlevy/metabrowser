---
type: is
id: is-01m84stgeegmf8gze6xawywk6m
title: "Rendered diff: audit every remaining content refusal, Markdown and structured"
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
created_at: 2026-11-23T18:13:50.662Z
updated_at: 2026-11-23T21:20:31.696Z
started_at: 2026-11-23T21:20:31.695Z
---
After task lists, raw HTML, footnotes and the separator, list every refusal left in markdown_projection.py and structured_projection.py (e.g. YAML/JSON with a duplicate key). Remove each that refuses content the document view renders; keep only measured cost bounds (size, nesting, deadline), each with its measurement.
