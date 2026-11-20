---
type: is
id: is-01m7jk9jrrvx502cp9gf9029cx
title: "Stack plan currency: Stack Order rows and phases for layers 23 to 28, status, references; move plan-2026-11-15 to specs/done when the top merges"
kind: task
status: closed
priority: 1
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/500
    at: 2026-11-20T17:03:35.643Z
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
parent_id: is-01m7hcanw7czjv3kgedg9zjbew
hold: null
hold_until: null
created_at: 2026-11-16T16:33:24.758Z
updated_at: 2026-11-20T17:59:12.019Z
started_at: 2026-11-16T21:06:43.696Z
closed_at: 2026-11-17T06:45:50.076Z
close_reason: "PR #500 merged at e442ed10d: plan-2026-11-15 moved to specs/done with Phases 29-31 ticked, Stack Order and references current; Review A dispositioned; CI green at 895cbb20c."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 511a0179-2c75-4418-a5a6-30e4d51c72ea
    linked_at: 2026-11-20T17:59:12.016Z
---
Reviewers noted the plan's Stack Order table lacks rows for pull requests 23 and 24 and that the rollout line drifted. Update in the top layer before the final merge.

## Notes

2026-11-17: PR #500 (branch claude/plan-2026-11-15-done, head 8f8816fb2) moves the plan to docs/project/specs/done/ with Status: Done. It ticks Phase 29 (mb-9ekj, #484 at f13d7cd25) and Phase 30 (mb-d0a3, mb-h0ml, mb-1l4i under mb-3zc8, #491 at ae554dda8). It adds row 31 and Phase 31 for mb-26zj (#487 at 6579c0d41), records the stack's merge commits under Stack Order, rewrites the Rollout Plan and the overview's out-of-stack paragraph, lists mb-xb2y, mb-i3df and mb-rlp4 under Non-Goals, and moves the plan to Done Plans in docs/project/README.md. The 74 beads whose spec_path named the old path were repointed to specs/done (statuses unchanged).
Still open, not ticked or closed here: mb-x1h6, mb-xz1r, mb-fon5, mb-4ydo, mb-cf0l and mb-z416 are in_progress although #445 and #451 merged at afda3599f; mb-r5jr is open although mb-xlla and mb-vg55 are closed; mb-xb2y, mb-i3df and mb-rlp4 are open follow-ups; mb-s3g8 is in_progress (its glyph shipped in #487). The Open Question on shared membership has no answer and no bead.
Close mb-p8et when #500 merges.
