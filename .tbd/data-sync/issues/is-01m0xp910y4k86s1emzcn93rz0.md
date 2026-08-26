---
type: is
id: is-01m0xp910y4k86s1emzcn93rz0
title: Delay Git hover preparation until stable intent while scrolling
kind: bug
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T00:07:18.301Z
updated_at: 2026-08-26T01:04:36.957Z
---
Implementation delays detail/comparison preparation until the existing stable-hover intent timer; transient mouseenter/leave churn starts no request. Click and Arrow selection pass the exact row, update only the previous and next selected/roving rows, apply the preview pending sheet and route synchronously, then cancel obsolete diff work and start or reuse selected preparation. Instrument that immediate O(1) block as gitRevision:selectionFeedback. The standard headed Git scenario must record that phase, require pending onset and clearance, and fail on route/selection/render divergence, blank frames, stuck busy state, missing phase attribution, or multiple mounts.

## Notes

Implemented stable-hover preparation, direct row passing, old/new-only selected-row mutation, and immediate phase attribution. Systematic headed profiling split selectionFeedback into pending, route, and rows, then rows into lookup/selection/anchor and the anchor into writes. It identified the new row tabindex write as the cold 267–398 ms forced-layout cost while a large retained diff was mounted; all other immediate operations measured 0–4 ms. The Tab anchor now finalizes after painted readiness as gitRevision:rowAnchor. Final fixed-corpus capture measured immediate spans 4.5/0.5/0.3 ms, pending onset 16.1/11.4/14.5 ms, row-anchor 8.1/0.4/4.5 ms, zero blank frames, exact convergence, one mount, bounded two-request hydration, and zero obsolete successes. Focused tests pass.
