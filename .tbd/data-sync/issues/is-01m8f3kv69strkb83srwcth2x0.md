---
type: is
id: is-01m8f3kv69strkb83srwcth2x0
title: Wait for file and folder link-card prefetch before starting the next one
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-link-preview-tooltips.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cte9rj7s82c4ywp7n3ph3z
hold: null
hold_until: null
created_at: 2026-11-27T18:17:22.375Z
updated_at: 2026-11-27T18:18:02.128Z
started_at: 2026-11-27T18:18:02.127Z
---
Independent follow-up on Metabrowser PR #912. The file and folder provider currently resolves before its shared counterpart request settles, so successive rests can start concurrent prefetches despite the documented limit.
