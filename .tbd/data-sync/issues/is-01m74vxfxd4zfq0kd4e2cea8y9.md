---
type: is
id: is-01m74vxfxd4zfq0kd4e2cea8y9
title: "PR #347 C3: history writer reads could-not-read as empty and overwrites the file"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:43.756Z
updated_at: 2026-11-11T09:41:57.932Z
closed_at: 2026-11-11T09:41:57.931Z
close_reason: "fixed in ecdaaa51: writer's own read leaves the file on transient errors and restarts only a foreign file; tests"
resolution: null
duplicate_of: null
---
Severity: Medium. PR #347 review C round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855769655). References: pull_snapshot_cache.py:33-38, :49-59, pull_record.py:527, :532.
