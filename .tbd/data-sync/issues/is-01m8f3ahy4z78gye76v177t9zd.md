---
type: is
id: is-01m8f3ahy4z78gye76v177t9zd
title: Dismiss pending and visible link cards on pointer press
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-link-preview-tooltips.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cte9rj7s82c4ywp7n3ph3z
hold: null
hold_until: null
created_at: 2026-11-27T18:12:17.986Z
updated_at: 2026-11-27T18:44:21.628Z
started_at: 2026-11-27T18:13:15.522Z
closed_at: 2026-11-27T18:44:21.628Z
close_reason: "Fixed and verified on Metabrowser PR #912, merged into main at fc79ace6bac718610eb9bf5a6d09cc244ecbc87c."
resolution: null
duplicate_of: null
---
Review J2 on Metabrowser PR #912. A press without a focus change must cancel the pending or visible tooltip for its own anchor.
