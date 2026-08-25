---
type: is
id: is-01m0vdjrk1qr4ezyt84tcvjbkv
title: "H59: Measure server event-loop availability during overlapping tally work"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m0tybgssytxdsdm4xtm6xn8h
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
hold: null
hold_until: null
created_at: 2026-08-25T02:56:51.287Z
updated_at: 2026-08-25T03:04:46.328Z
started_at: 2026-08-25T02:58:48.363Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
Extend the installed-build backend comparison before changing production code. Start a full root tally while overlapping row traffic is active, probe /api/index/progress, and record tally_overlap_progress_max_ms plus sample count. Add a deterministic 350 ms lock-contention regression that measures the asyncio heartbeat. Capture c123ae6 as the failing control; the candidate target is less than 50 ms max event-loop delay without changing rows or tallies.

## Notes

Coverage added before production changes. Deterministic control: a 350 ms held tally lock made navigation_tallies_fresh_within take 352 ms. Installed-server control on the 123,657-file/15,601-directory project corpus: tally 461.4 ms, overlapping row max 432.8 ms, /api/index/progress max 393.3 ms across two overlap samples. Candidate gate is less than 50 ms and zero samples invalidate a comparison.
