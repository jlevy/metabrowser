---
type: is
id: is-01m0vdjrk1qr4ezyt84tcvjbkv
title: "H59: Measure server event-loop availability during overlapping tally work"
kind: task
status: closed
priority: 1
version: 8
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
updated_at: 2026-08-25T03:09:32.752Z
started_at: 2026-08-25T02:58:48.363Z
closed_at: 2026-08-25T03:09:32.751Z
close_reason: Added and validated the installed-build tally-overlap comparison and hard candidate gate, added the deterministic heartbeat regression, and recorded the failing c123ae6 control before changing production code.
resolution: null
duplicate_of: null
---
Extend the installed-build backend comparison before changing production code. Start a full root tally while overlapping depth-0 tally traffic is active, probe /api/index/progress, and record tally_overlap_progress_max_ms plus sample count. Add a deterministic 350 ms lock-contention regression that measures the asyncio heartbeat. Capture c123ae6 as the failing control. The deterministic cache-probe budget is less than 50 ms; the installed-server gate is less than 200 ms, matching the browser responsiveness boundary.

## Notes

Coverage added before production changes. Deterministic control: a 350 ms held tally lock made navigation_tallies_fresh_within take 352 ms. Installed-server control on the 123,657-file project corpus: 317.4 ms maximum /api/index/progress latency while two depth-0 tally requests overlap. Two development-candidate runs after the nonblocking probe record 61.5 ms and 109.9 ms. Zero samples invalidate the comparison.
