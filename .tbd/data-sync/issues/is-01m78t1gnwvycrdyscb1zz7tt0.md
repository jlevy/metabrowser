---
type: is
id: is-01m78t1gnwvycrdyscb1zz7tt0
title: "Flaky: tests/test_transitions_instrument.py Chrome recorder on CI"
kind: bug
status: open
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-12T21:18:56.186Z
updated_at: 2026-11-14T18:44:57.948Z
---
The real-Chrome transitions recorder test (tests/test_transitions_instrument.py, tests/dom/transitions-recorder-chrome.mjs) failed intermittently on CI. Three causes are fixed on main: #381 (mb-054f) rewrote the 'a long ready frame counts its own rendering: X vs Y' assertion, #415 (mb-p34w) retries a check whose frame clock alone was refused, and #427 (mb-1n44) stops each Chrome test's whole process group and gives it its own profile.

Still open:
1. 'Chrome did not publish a DevTools endpoint within 30 s' (explorations/performance-loop/transitions-recorder.mjs, launchBrowser endpointTimeoutMs) failed test_transition_recorder_in_chrome[frames-5] in four CI runs on 2026-11-13, two of them on main (43468651462, 43477997216). None appeared in failed runs after #427 merged on 2026-11-14. Find out whether #427 removed the cause before changing the bound.
2. The CI test matrix (.github/workflows/ci.yml, job test) keeps the default fail-fast, so one flaky job cancels the other three Python jobs and a run reads as four failures. Decide whether it should set fail-fast: false, as the admitted-git job does.

## Notes

2026-11-12: also failed in the stack-integration job of run 43309191807 (head eb3f2f69): 'a long ready frame counts its own rendering: 663.2 vs 673', 1 failed and 5401 passed. And again in test (3.14t) of run 43311693860 (head 61169c43): '430.4 vs 441.4', 1 failed and 5401 passed; fail-fast cancelled the 3.12, 3.13, and 3.14 jobs. Four of the branch's five runs hit it, on two different jobs, always this one assertion or the Chrome DevTools start; failed jobs re-run.
