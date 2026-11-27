---
type: is
id: is-01m8f3kv69strkb83srwcth2x0
title: Wait for file and folder link-card prefetch before starting the next one
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
created_at: 2026-11-27T18:17:22.375Z
updated_at: 2026-11-27T18:44:21.650Z
started_at: 2026-11-27T18:18:02.127Z
closed_at: 2026-11-27T18:44:21.650Z
close_reason: "Fixed and verified on Metabrowser PR #912, merged into main at fc79ace6bac718610eb9bf5a6d09cc244ecbc87c."
resolution: null
duplicate_of: null
---
Independent follow-up on Metabrowser PR #912. The file and folder provider currently resolves before its shared counterpart request settles, so successive rests can start concurrent prefetches despite the documented limit.
