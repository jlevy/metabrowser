---
type: is
id: is-01kxnx9whay0pcjvvqk0s3k785
title: Support multiplexed fair tail streaming
kind: feature
status: open
priority: 2
version: 3
spec_path: TODO.md
labels:
  - streaming
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:05.578Z
updated_at: 2026-08-16T08:06:00.564Z
extensions:
  linear:
    id: 455d47a1-b9ed-4da0-a5e5-be31bcf0b4a2
    linked_at: 2026-08-16T08:06:00.564Z
---
Extend live streaming from one file to a bounded multiplexed tail across selected files. Define backpressure, fairness, reconnection cursors, truncation/rotation semantics, per-file errors, resource caps, and browser rendering before exposing the API.
