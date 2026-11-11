---
type: is
id: is-01m74vxg9th8tce1nv1zqt09y0
title: "PR #347 C4: reader-scoped retention depends on whether another reader's write had a comparison"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:44.153Z
updated_at: 2026-11-11T09:41:58.252Z
closed_at: 2026-11-11T09:41:58.251Z
close_reason: "fixed in ecdaaa51: every store-backed write keeps only its reader's pairs; both R2 paths tested"
resolution: null
duplicate_of: null
---
Severity: Low. PR #347 review C round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855769655). References: pull_snapshot_cache.py:51, pull_record.py:528, :531, pull_snapshot.py:139.
