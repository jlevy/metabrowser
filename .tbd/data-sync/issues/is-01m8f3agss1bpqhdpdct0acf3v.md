---
type: is
id: is-01m8f3agss1bpqhdpdct0acf3v
title: Preserve title-based image names in link cards
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-link-preview-tooltips.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cte9rj7s82c4ywp7n3ph3z
hold: null
hold_until: null
created_at: 2026-11-27T18:12:16.817Z
updated_at: 2026-11-27T18:44:21.610Z
started_at: 2026-11-27T18:13:15.503Z
closed_at: 2026-11-27T18:44:21.607Z
close_reason: "Fixed and verified on Metabrowser PR #912, merged into main at fc79ace6bac718610eb9bf5a6d09cc244ecbc87c."
resolution: null
duplicate_of: null
---
Review J1 on Metabrowser PR #912. A link containing text and a separately titled image loses the image name in the accessibility tree when the hover card takes both titles.
