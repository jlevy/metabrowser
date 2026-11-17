---
type: is
id: is-01m7kpmfhmfryhsb2eg3fg7jyp
title: "CI speed 1.5: add make ci-report, which prints each CI job's median and 90th percentile and the run's push-to-green from gh run data"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpncy9xzk6a0rhv0vxd4db
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T02:51:02.067Z
updated_at: 2026-11-17T04:48:06.066Z
started_at: 2026-11-17T04:48:06.066Z
---
Phase 1 of plan-2026-11-16-fast-ci.md. Makes the tables of research-2026-11-16-ci-speed.md a command, so each phase is verified the same way and no baseline is written into prose that nothing maintains. Inputs: gh run list and the jobs of each attempt. Outputs: per-job and per-step median and 90th percentile over successful jobs, push-to-green for first attempts, runner minutes, reruns, and with --check a failure when a job's 90th percentile passes 80 percent of its timeout-minutes. Tested against recorded JSON, not the network.
