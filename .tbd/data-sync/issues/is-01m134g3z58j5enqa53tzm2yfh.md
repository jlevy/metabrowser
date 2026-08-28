---
type: is
id: is-01m134g3z58j5enqa53tzm2yfh
title: "D4: status generation churns on unrelated terminal Git commands"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/reviews/review-2026-08-27-independent-design-review.md
labels: []
dependencies: []
parent_id: is-01m134g1jm1dr1xgfhct0ja3c7
created_at: 2026-08-28T02:52:02.915Z
updated_at: 2026-08-28T03:02:50.299Z
closed_at: 2026-08-28T03:02:50.298Z
close_reason: Fixed in dbd5521 (D4). See the commit message and the plan diff.
resolution: null
duplicate_of: null
---
The list generation hashes resolved per-worktree index identity. Plain terminal git status rewrites the index (verified on git 2.50.1 in this session), so a user running git status in a terminal churns the generation with no content change, causing spurious ETag misses, 409 stale_status, and diff re-materialization. The normalized sorted records plus HEAD already capture every change the index identity was meant to catch; drop the stat identity from the hash.
