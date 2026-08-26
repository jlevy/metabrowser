---
type: is
id: is-01m0xp910y4k86s1emzcn93rz0
title: Delay Git hover preparation until stable intent while scrolling
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T00:07:18.301Z
updated_at: 2026-08-26T00:07:32.429Z
---
User acceptance regression on PR #82. scheduleHover starts prepareRevision immediately on mouseenter even though tooltip presentation waits 300 ms. Scrolling the Git panel moves many rows under a stationary pointer, repeatedly starting and aborting detail/comparison work and competing with the selected revision, so the nav feels delayed. Files/functions: src/metabrowser/static/git-panel.js scheduleHover/cancelHover/moveCommitRowFocus/selectCommit; tests/dom/git-panel-behavior.js; explorations/performance-loop/capture-browser.js if the standard scenario needs a scroll-intent assertion. Behavior: row focus, selected state, and scroll position paint immediately; speculative detail/comparison work starts only after stable hover intent, while click/keyboard selection starts or reuses selected work immediately; superseded intent launches no network work; selected/route/rendered convergence and one-mount invariant remain. Acceptance: TDD reproduces churn before the fix, rapid row enter/leave during scroll launches no preparations, a stable hover launches one bounded preparation, click and Arrow navigation remain immediate, and focused/full/real-browser gates pass.
