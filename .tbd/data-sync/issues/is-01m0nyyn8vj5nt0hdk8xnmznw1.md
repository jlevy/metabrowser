---
type: is
id: is-01m0nyyn8vj5nt0hdk8xnmznw1
title: "H49: measure the four unrecorded regimes — interaction, churn, memory, warm reopen"
kind: task
status: open
priority: 0
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0m5vwhzn3h5bxyy79w3st82
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:05:00.315Z
updated_at: 2026-11-14T18:43:00.848Z
---
Load-time hypothesis H49 (plan-2026-08-21-load-time-performance.md, Hypotheses). Four regimes the cold-load metric cannot see hide regressions: interaction latency, churn recovery, resident size, and warm reopen. Harness 4 records the fields (Event Timing, bounded retention, optional JS heap). The scenario runs, the churn and reopen adapters, and the baselines remain. Gates H21 (mb-omhf).
