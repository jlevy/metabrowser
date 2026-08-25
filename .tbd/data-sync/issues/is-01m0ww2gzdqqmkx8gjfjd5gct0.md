---
type: is
id: is-01m0ww2gzdqqmkx8gjfjd5gct0
title: Cancel retained diff background work during revision handoff
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T16:29:22.269Z
updated_at: 2026-08-25T16:54:47.889Z
closed_at: 2026-08-25T16:54:47.888Z
close_reason: "Fixed and validated in pushed commit 9ce7f2e: obsolete retained diff work is canceled immediately, deferred hydration is viewport-gated and capped at two active requests, visible DOM remains until atomic replacement, and focused/full/real-browser validation passes."
resolution: null
duplicate_of: null
---
Regression on PR #82. In src/metabrowser/static/git-panel.js selectCommit, a previous diff is deliberately retained until its replacement mounts, but its deferred per-file hydration and syntax work continue. A large revision can therefore saturate the server with obsolete /api/plugin/diff/comparison?revision=<old>&file=<path> requests; selection and /commit/<new> advance while the visible .git-commit-view remains on the old revision for many seconds. Reproduced on the trading corpus: revisions 0-9 mounted, selection 10 moved to 563f3440 while the view remained 7282a597; logs showed old-revision hydration requests taking 5-13 seconds and the new comparison taking 9.3 seconds. Files/functions: src/metabrowser/builtin_plugins/diff/diff-view.js mountDiffView lifecycle handle and its pending-work cancellation; src/metabrowser/static/git-panel.js selectCommit/renderCommitDetail mounted-handle ownership; tests/dom/diff-view-behavior.js and tests/dom/git-panel-behavior.js. Behavior/invariants: starting a new selected revision immediately aborts pending hydration/syntax/timers for the retained diff without removing its already-rendered DOM; final disposal remains idempotent and removes it after the atomic swap; stale selections cannot cancel the replacement. Acceptance: focused tests fail before/fix after; a visible-browser sequential stress pass keeps selected, route, and mounted revision convergent without obsolete old-revision requests delaying the replacement; make format and make verify pass.

## Notes

Fixed in 9ce7f2e and pushed to PR #82. The retained diff lifecycle now separates cancelPending from final dispose; new selection aborts active hydration and syntax work, disconnects IntersectionObserver, clears queued hydration, timers, and cooperative yielders, and retains the existing DOM until atomic replacement. Deferred sections become eligible only in the visible scroll area and at most two requests run concurrently, based on a Chrome 151 measurement where an 88-file comparison exposed 24 sections after a bottom jump. Focused Git/diff browser tests, make format, make verify (1,546 pytest cases and 48 golden scenarios), pre-commit, pre-push, a 16-revision visible stress pass, and the exact-head headed git-revisions scenario all pass. Exact head 9ce7f2e records 632.8 ms and 273.1 ms cold transitions, 96.5 ms prepared with no click-time fetch, zero blank frames, one mounted comparison, and zero page exceptions.
