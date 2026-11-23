---
type: is
id: is-01m84stepzwezjehjw1rexrwj8
title: "Rendered diff: show a file with footnotes"
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
created_at: 2026-11-23T18:13:48.894Z
updated_at: 2026-11-23T19:36:30.229Z
started_at: 2026-11-23T19:36:30.228Z
---
markdown_projection.py refuses any file with footnotes (footnotes) because they render away from their source. Project references in place and definitions as blocks matched to their source lines.
