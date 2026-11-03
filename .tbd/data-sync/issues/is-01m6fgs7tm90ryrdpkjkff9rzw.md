---
type: is
id: is-01m6fgs7tm90ryrdpkjkff9rzw
title: "PR #281: rerun the page-open pairs after the ask delay"
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6fgs20qmf639pkqec7tzk5q
created_at: 2026-11-03T01:36:06.995Z
updated_at: 2026-11-03T02:16:41.573Z
closed_at: 2026-11-03T02:16:41.571Z
close_reason: "done: 41 back-to-back pairs at 0c6f09a5 against 75627cb6, load 4.7 to 7.6: first card 0.991 and 0.989, first Markdown 0.998 and 0.983; pin by ID 1.056"
resolution: null
duplicate_of: null
---
Review A's Performance note: pairs were on a loaded machine and not rerun after REFRESH_ASK_MS. Back-to-back before and after, 1.3x rough cut and 1.1x careful, if load is under about 8.
