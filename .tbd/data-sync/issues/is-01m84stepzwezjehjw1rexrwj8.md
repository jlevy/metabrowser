---
type: is
id: is-01m84stepzwezjehjw1rexrwj8
title: "Rendered diff: show a file with footnotes"
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
created_at: 2026-11-23T18:13:48.894Z
updated_at: 2026-11-23T22:03:38.610Z
started_at: 2026-11-23T19:36:30.228Z
closed_at: 2026-11-23T22:03:38.609Z
close_reason: "Footnotes render in Rendered: a reference in place, numbered as the Document view numbers it, each note a block of its definition's lines (_footnotes_in_place); notes no line holds make the side one block of KPress's render. Commit 2455dcdf3, PR #766."
resolution: null
duplicate_of: null
---
markdown_projection.py refuses any file with footnotes (footnotes) because they render away from their source. Project references in place and definitions as blocks matched to their source lines.
