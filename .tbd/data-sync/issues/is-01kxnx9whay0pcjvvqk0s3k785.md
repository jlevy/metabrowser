---
type: is
id: is-01kxnx9whay0pcjvvqk0s3k785
title: Support multiplexed fair tail streaming
kind: feature
status: open
priority: 2
version: 5
spec_path: TODO.md
labels:
  - streaming
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:05.578Z
updated_at: 2026-11-20T19:15:56.985Z
extensions: {}
---
Extend live streaming from one file to a bounded multiplexed tail across selected files. Define backpressure, fairness, reconnection cursors, truncation/rotation semantics, per-file errors, resource caps, and browser rendering before exposing the API.

## Notes

2026-11-14 audit: events.py:5 and server.py:1109 already name a 'multiplexed /api/tail' that no route serves.
