---
type: is
id: is-01m7kpncy9xzk6a0rhv0vxd4db
title: "CI speed 2.4: add a nightly workflow that runs the serial and Chrome tiers five times on main and reports each job's time against its limit"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:32.168Z
updated_at: 2026-11-17T04:22:28.026Z
---
Phase 2 of plan-2026-11-16-fast-ci.md, Flakes and Time Limits; the owner approved it (Q1). schedule and workflow_dispatch, the same pinned actions, contents: read. Five repetitions of make test-serial and of the four test-chrome shards on main, on Python 3.13, the interpreter a pull request draws on: any failure fails the run and names the test, so a flake is found away from a pull request. It finds flakes; the runs on each commit of main are the coverage. Then make ci-report --check, which fails when a job's 90th percentile passes 80 percent of its timeout-minutes. Accept on one workflow_dispatch run: 5 serial-tier jobs and 20 Chrome shard jobs run and report. A red main is decided (Q6, 2026-11-17: a red main widens a pull request's run, and the merging agent merges by main's state; mb-oz36). Who reads a red nightly is Q9, open; the proposal is that the merging agent reads the newest nightly run when it starts merging and gives each failure a bead. Add no issues: write permission.

## Notes

2026-11-16: the owner answered plan Q1: the nightly soak workflow is approved, through a reviewed pull request (relayed by the coordinating session). Q6, who is told of a red nightly or main, is open; add no issues: write permission.

2026-11-17: Q6 is decided for main (a red main widens a pull request's run, and the merging agent merges by main's state; see mb-oz36). Who reads a red nightly is now Q9, open. The soak runs the serial and Chrome tiers, after the Q3 narrowing of review A on #496.
