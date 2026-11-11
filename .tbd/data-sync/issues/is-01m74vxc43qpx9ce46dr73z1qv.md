---
type: is
id: is-01m74vxc43qpx9ce46dr73z1qv
title: "PR #347 A15: each snapshot request parses the whole PR record and spawns two Git processes"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:39.874Z
updated_at: 2026-11-11T09:41:54.629Z
closed_at: 2026-11-11T09:41:54.629Z
close_reason: "fixed in ecdaaa51: admission memo by file stamps and commit-to-tree memo; subject LRU not adopted (loop-bound actors, no plugin shutdown hook)"
resolution: null
duplicate_of: null
---
Severity: Low. PR #347 review A round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855504972). References: pull_snapshot.py:124-125, :282-287, pull_record.py:516-517.
