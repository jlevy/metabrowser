---
type: is
id: is-01m2yskh8x4qq1fhn4np7xsfp3
title: "PR 216 R3: bound cat-file actor transactions by the batch policy deadline"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yryd6had8zdvj8eag4a4v4
hold: null
hold_until: null
created_at: 2026-09-20T06:56:06.428Z
updated_at: 2026-09-20T07:15:20.205Z
started_at: 2026-09-20T06:57:40.740Z
closed_at: 2026-09-20T07:15:20.204Z
close_reason: "Fixed in bc8dd72b: batch cat-file info/info_many honor BATCH_OBJECT_POLICY.timeout_s and poison the actor."
resolution: null
duplicate_of: null
---
src/metabrowser/git/tree_source.py _BatchObjectReader.info_many and _transact never enforce BATCH_OBJECT_POLICY.timeout_s. A stalled actor can occupy pool slots indefinitely. Enforce deadline, poison the actor, surface GitTimeoutError, and test replacement after timeout.
