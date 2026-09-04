---
type: is
id: is-01m1mv98vsehmmnp2p3ts42gyy
title: "PR #101 R5c: the fast-copy guard misses an appended field"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:21.144Z
updated_at: 2026-09-04T02:07:13.701Z
closed_at: 2026-09-04T02:07:13.699Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
events.py:119-131 claims test_fsentry_fast_copies_match_dataclasses_replace fails when a field is added; empirically a field appended with a default passes while both fast copies silently drop it. _internal_entry's 19-argument positional build has no guard at all. Build the probe reflectively from dataclasses.fields with distinct sentinels.
