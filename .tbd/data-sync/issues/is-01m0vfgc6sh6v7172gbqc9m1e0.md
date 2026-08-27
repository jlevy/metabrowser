---
type: is
id: is-01m0vfgc6sh6v7172gbqc9m1e0
title: "H61: Cooperatively yield during full navigation-tally passes"
kind: bug
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m0vdm7d6j696m0acyqxsq215
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
hold: null
hold_until: null
created_at: 2026-08-25T03:30:30.232Z
updated_at: 2026-08-27T00:18:17.824Z
started_at: 2026-08-25T03:30:49.753Z
---
The first exact v0.6.0-to-5a8f3ed installed comparison invalidated one of five candidate runs: tally-overlap progress latency reached 291.7 ms against the 200 ms release gate while the tally pass stretched to 928.9 ms. The nonblocking memo probe removed the lock wait, but the O(index) Python worker can still hold enough CPU/GIL time under a cold tail to starve the request loop. Add measured cooperative yield points to the tally pass, a deterministic heartbeat regression that lengthens the interpreter switch interval, and re-run the exact comparison. Preserve ordered rows/tallies and record both the failed and corrected ranges.

## Notes

Release PR #85 CI reproduced the H61 heartbeat at 52.11 ms on Python 3.12/Linux, narrowly above the specified 50 ms deterministic guard. Tightened the cooperative yield cadence from 2,048 to 1,024 entries; ten consecutive focused local runs pass. Re-run the exact v0.7.1 release comparison and full release gates before closing.
