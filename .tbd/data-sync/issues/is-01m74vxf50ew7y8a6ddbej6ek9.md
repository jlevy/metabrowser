---
type: is
id: is-01m74vxf50ew7y8a6ddbej6ek9
title: "PR #347 C1: CAS reads a failed pre-read as an observation; transient read error makes refresh a no-op reporting success"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:42.975Z
updated_at: 2026-11-11T09:41:57.252Z
closed_at: 2026-11-11T09:41:57.251Z
close_reason: "fixed in ecdaaa51: only a record or not_cached counts as an observation; R7 test"
resolution: null
duplicate_of: null
---
Severity: Medium. PR #347 review C round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855769655). References: pulls.py:913, :950, :966, pull_record.py:553-554, :516-519.
