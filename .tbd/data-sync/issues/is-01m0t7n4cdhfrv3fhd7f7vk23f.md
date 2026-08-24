---
type: is
id: is-01m0t7n4cdhfrv3fhd7f7vk23f
title: Investigate merged-main cold-start shell-paint tail variance
kind: task
status: open
priority: 2
version: 1
labels:
  - performance
dependencies: []
created_at: 2026-08-24T15:54:03.020Z
updated_at: 2026-08-24T15:54:03.020Z
---
Post-merge validation on bae51fd found one of four candidate browser cold loads at 996 ms FCP / 1,097 ms first row, while the other three were 132-192 ms FCP / 168-286 ms first row. Candidate FCP median was 178 ms versus v0.6.0 164 ms with overlapping ranges; backend spawn also had one 1.831 s candidate outlier. Responsiveness remained clean (0 long tasks, <=24 ms measured input latency) and all hard gates passed. Reproduce and attribute cold server/shell startup tail latency without weakening the responsiveness gates.
