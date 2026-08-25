---
type: is
id: is-01m0wycyj5gpp5gh1eyczfcrcp
title: Gate Git revision validation on deferred request storms
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T17:10:01.028Z
updated_at: 2026-08-25T18:15:12.636Z
closed_at: 2026-08-25T18:15:12.635Z
close_reason: "Implemented the automatic deferred request-storm gate, validated it on the exact pushed head, documented it in the standard performance process, and updated PR #82."
resolution: null
duplicate_of: null
---
Add a standard acceptance guard for the regression evidenced by preserved console logs from 2026-08-25T15:26Z. Files/functions: src/metabrowser/static/perf.js fetch wrapper/snapshot/reset; explorations/performance-loop/capture-browser.js runGitRevisionScenario plus a deferred-hydration stress phase and pure validator; tests/dom/perf-behavior.js; tests/test_browser_performance_capture.py; docs/web-performance-framework.md; explorations/performance-loop/README.md; active plan. Behavior/invariants: the profiler records the exact maximum simultaneous application fetches for a measurement window; the Git scenario finds a sufficiently deferred revision on its real corpus, resets measurement, makes deferred work visible, verifies no more than two concurrent hydration requests, changes revision while work is active, rejects any successful obsolete per-file completion after selection, and requires selected/URL/rendered convergence with one mount. The scenario must fail loudly when the corpus cannot exercise deferred hydration rather than report a false pass. Acceptance: focused tests fail before/fix after; a fresh-origin headed scenario on the 310-file revision rejects the old fanout and passes the fixed scheduler; make format and make verify pass; PR validation states the new automatic gate.

## Notes

Implemented and pushed in commit 0d9d358. The exact committed-head headed Git scenario on the trading corpus found 110 pending file sections, observed deferred concurrency 2 and application concurrency 3, aborted both active obsolete requests, recorded zero obsolete successes and zero concurrency-attribution overflow, and converged selected row, route, and rendered revision on one mounted comparison with zero page exceptions and zero blank frames. Exact-head transitions were 639.2 ms and 1088.2 ms cold plus 78.3 ms pointer-prepared with no click-time fetch; cold results remain variable and carry no new speed claim. Focused suite passed 52 tests. make format and make verify passed; make verify covered 1550 pytest tests and 48 golden scenarios. The pre-push hook repeated the full gate successfully. PR #82 description and validation plan now document the standard automatic gate and exact-head evidence. Formal reviews, inline comments, general comments, linked issues and review documents contain no new actionable feedback.
