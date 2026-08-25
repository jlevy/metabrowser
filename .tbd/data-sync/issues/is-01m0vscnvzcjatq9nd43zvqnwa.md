---
type: is
id: is-01m0vscnvzcjatq9nd43zvqnwa
title: Design and implement scalable Git history continuation
kind: task
status: open
priority: 1
version: 2
labels:
  - release:v0.8.0
dependencies:
  - type: blocks
    target: is-01m0vsd8dnak6hw2b87x5awch6
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:14.801Z
updated_at: 2026-08-25T06:23:33.811Z
---
Replace or justify the offset-based continuation path so page cost does not grow unacceptably with depth. Keep cursors opaque, reject malformed or stale continuation safely, preserve topological ordering and merge branches, bound each Git subprocess by time and bytes, and add repository-level pagination tests across branching, moved refs, empty history, and deep continuation.
