---
type: is
id: is-01m78t1gnwvycrdyscb1zz7tt0
title: "Flaky: tests/test_transitions_instrument.py Chrome recorder on CI"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-12T21:18:56.186Z
updated_at: 2026-11-12T21:18:56.186Z
---
The real-Chrome transitions recorder test fails intermittently on the GitHub Actions test (3.14t) job, and fail-fast then cancels the other three test jobs, so a run looks like four failures. Seen on main (run 43232779342, 2026-11-12) and twice on claude/plugin-sources-design-9e15c5 (runs 43279678586 and 43283551521), whose delta is documentation and explorations only. Messages: 'Error: Chrome did not publish a DevTools endpoint within 30 s' (explorations/performance-loop/transitions-recorder.mjs:1067) and 'a long ready frame counts its own rendering: 613.2 vs 625.4' (tests/test_transitions_instrument.py:52). Decide whether the timing assertion needs a tolerance, the Chrome start a longer bound, or the test a retry, and whether the matrix should keep fail-fast.
