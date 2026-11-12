---
type: is
id: is-01m78t1gnwvycrdyscb1zz7tt0
title: "Flaky: tests/test_transitions_instrument.py Chrome recorder on CI"
kind: bug
status: open
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-12T21:18:56.186Z
updated_at: 2026-11-12T21:50:09.892Z
---
The real-Chrome transitions recorder test fails intermittently on the GitHub Actions test (3.14t) job, and fail-fast then cancels the other three test jobs, so a run looks like four failures. Seen on main (run 43232779342, 2026-11-12) and twice on claude/plugin-sources-design-9e15c5 (runs 43279678586 and 43283551521), whose delta is documentation and explorations only. Messages: 'Error: Chrome did not publish a DevTools endpoint within 30 s' (explorations/performance-loop/transitions-recorder.mjs:1067) and 'a long ready frame counts its own rendering: 613.2 vs 625.4' (tests/test_transitions_instrument.py:52). Decide whether the timing assertion needs a tolerance, the Chrome start a longer bound, or the test a retry, and whether the matrix should keep fail-fast.

## Notes

2026-11-12: also failed in the stack-integration job of run 43309191807 (head eb3f2f69): 'a long ready frame counts its own rendering: 663.2 vs 673', 1 failed and 5401 passed. And again in test (3.14t) of run 43311693860 (head 61169c43): '430.4 vs 441.4', 1 failed and 5401 passed; fail-fast cancelled the 3.12, 3.13, and 3.14 jobs. Four of the branch's five runs hit it, on two different jobs, always this one assertion or the Chrome DevTools start; failed jobs re-run.
