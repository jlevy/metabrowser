---
type: is
id: is-01m84stgeegmf8gze6xawywk6m
title: "Rendered diff: audit every remaining content refusal, Markdown and structured"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-23T18:13:50.662Z
updated_at: 2026-11-23T22:03:42.212Z
started_at: 2026-11-23T21:20:31.695Z
closed_at: 2026-11-23T22:03:42.203Z
close_reason: 'Audit done: non-UTF-8 bytes, NUL and lone carriage returns render (patch lines checked by exact bytes, Git lines split where MarkdownIt ends one); JSON with a key twice reads last-wins as the tree view does, hidden values flagged source_only; YAML duplicates stay refused as the tree view refuses them. Kept: measured cost bounds, nesting, deadline, and patch/render-tree checks no checkout Markdown file reaches. Remaining: YAML 1 and "1" in one mapping, refused by the shared bounded loader. Commit 7ad9df05a, PR #766.'
resolution: null
duplicate_of: null
---
After task lists, raw HTML, footnotes and the separator, list every refusal left in markdown_projection.py and structured_projection.py (e.g. YAML/JSON with a duplicate key). Remove each that refuses content the document view renders; keep only measured cost bounds (size, nesting, deadline), each with its measurement.
