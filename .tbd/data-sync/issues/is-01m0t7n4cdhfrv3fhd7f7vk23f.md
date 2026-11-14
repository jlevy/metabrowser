---
type: is
id: is-01m0t7n4cdhfrv3fhd7f7vk23f
title: Investigate merged-main cold-start shell-paint tail variance
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels:
  - performance
dependencies:
  - type: blocks
    target: is-01m0vcqjmdqs2zhk804rgbjjm9
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-24T15:54:03.020Z
updated_at: 2026-11-14T18:44:03.717Z
closed_at: 2026-11-14T18:44:03.716Z
close_reason: "Not reproduced: the single 996 ms FCP run on bae51fd (exp-015) did not recur in the v0.7.1 or v0.8.0 comparisons (exp-017, exp-019, FCP at most 192 ms), and H57 attributed the shell boot (mb-emhr)."
resolution: canceled
duplicate_of: null
---
Post-merge validation on bae51fd found one of four candidate browser cold loads at 996 ms FCP / 1,097 ms first row, while the other three were 132-192 ms FCP / 168-286 ms first row. Candidate FCP median was 178 ms versus v0.6.0 164 ms with overlapping ranges; backend spawn also had one 1.831 s candidate outlier. Responsiveness remained clean (0 long tasks, <=24 ms measured input latency) and all hard gates passed. Reproduce and attribute cold server/shell startup tail latency without weakening the responsiveness gates.
