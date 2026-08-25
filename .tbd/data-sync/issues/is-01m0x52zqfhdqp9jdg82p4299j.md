---
type: is
id: is-01m0x52zqfhdqp9jdg82p4299j
title: Deduplicate selected file and hover-prefetch requests
kind: bug
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0x3skec67w78kafbez3xj2d
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T19:06:54.563Z
updated_at: 2026-08-25T19:11:20.451Z
closed_at: 2026-08-25T19:11:20.443Z
close_reason: The performance loop now rejects duplicate matching file requests; selection cancels matching hover timers, joins matching in-flight prefetch, aborts unrelated speculation, and preserves stale-claim safety. Focused tests pass and a headed fixed-corpus rerun recorded one request per cold transition, zero cached requests, zero blank frames, exact convergence, and no page exceptions.
resolution: null
duplicate_of: null
---
Measured finding from the headed file-views scenario on a fixed large project corpus: selecting one source file issued two concurrent matching /api/file requests. The selected request ran about 454 ms; the row-hover timer fired 250 ms later and duplicated it for about 208 ms, with both completing together. Files/functions: src/metabrowser/static/app.js hoverPrefetchTimer/hoverPrefetchPath/hoverPrefetchController/hoverPrefetchPromise/startHoverPrefetch/abortHoverPrefetch/settleHoverPrefetchForSelection/selectFile; tests/test_quick_file_integration.py; explorations/performance-loop/capture-browser.js measureFileTransition/assertFileTransitionHealth; tests/test_browser_performance_capture.py; active plan and changelog. Behavior/invariants: selection immediately cancels an unstarted matching hover timer, joins an already-active matching prefetch, aborts unrelated speculative work, and then reads the populated cache or issues exactly one selected request after a failed prefetch. Cold transitions allow at most one path-matching /api/file request; cached revisits allow zero. Pending feedback and preview-claim races remain correct. Acceptance: focused failing tests before/fix after; headed file-views run reports one request for cold source/Markdown, zero for cached revisit, zero blank frames, exact convergence, and no page exception; make format and make verify pass under final validation.
