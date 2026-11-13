---
type: is
id: is-01m7a35r94hjrmb4ck663bh1wf
title: Transition recorder Chrome test fails when a slow CI runner's frame clock is refused
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T09:17:46.659Z
updated_at: 2026-11-13T09:17:46.659Z
---
tests/test_transitions_instrument.py::test_transition_recorder_in_chrome[frames2-3] failed on CI (run 43392954136, job 131777006170, head ea171fc0 of #378, which does not touch the recorder): 'a long ready frame counts its own rendering: [[frame_clock, median frame step 416.6 ms over the window]]'. The recorder correctly refuses a window whose frame clock is not running, but the test treats that guard refusal on a throttled runner as a failure. The next run on the same branch passed. Fix: when the check's only refusal is the frame-clock guard, retry the case or skip it with the guard's reason, so the test fails only on a wrong measurement, not on a runner that cannot measure.
