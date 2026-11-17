---
type: is
id: is-01m7kpncy9xzk6a0rhv0vxd4db
title: "CI speed 2.4: add a nightly workflow that runs the serial tier five times on main and reports each job's time against its limit"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:32.168Z
updated_at: 2026-11-17T03:05:26.696Z
---
Phase 2 of plan-2026-11-16-fast-ci.md, Flakes and Time Limits; needs the owner's answer to Q1. schedule and workflow_dispatch, the same pinned actions, contents: read. Five repetitions of the four serial shards on main: any failure fails the run and names the test, so a Chrome flake is found away from a pull request. Then make ci-report --check, which fails when a job's 90th percentile passes 80 percent of its timeout-minutes. Who is told of a red nightly or a red main is Q6.

## Notes

2026-11-16: the owner answered plan Q1: the nightly soak workflow is approved, through a reviewed pull request (relayed by the coordinating session). Q6, who is told of a red nightly or main, is open; add no issues: write permission.
