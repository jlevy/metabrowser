---
type: is
id: is-01m0nyyk9af0a9wrtfy3b5t70r
title: "H44: measure and engineer the remote-link regime (RTT knob, batched prefetch, zstd)"
kind: task
status: open
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:58.282Z
updated_at: 2026-11-14T18:47:39.942Z
---
Load-time hypothesis H44 (plan-2026-08-21-load-time-performance.md, Hypotheses). Under realistic latency, batching the subtree prefetch into one request beats the server-side wins, because ~110 requests over six HTTP/1.1 connections are priced at localhost and paid in round trips. Metric: first_row_ms and total prefetch time at 0 ms and 120 ms RTT. If it holds: one batched tree request in place of up to 32, zstd, and an encoded-body cache per revision (H25, mb-43v7). Supersedes the framing of H26 (mb-f591).
