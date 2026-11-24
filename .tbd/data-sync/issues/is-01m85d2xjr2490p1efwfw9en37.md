---
type: is
id: is-01m85d2xjr2490p1efwfw9en37
title: "PR #768 A7: stale RepositoryTooLargeError docstring"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m85d2hj4x5fmcx1vdke1637w
hold: null
hold_until: null
created_at: 2026-11-23T23:50:29.207Z
updated_at: 2026-11-24T00:16:49.309Z
started_at: 2026-11-23T23:50:50.765Z
closed_at: 2026-11-24T00:16:49.309Z
close_reason: "fixed in da974d24: RepositoryTooLargeError docstring no longer speaks of a size limit"
resolution: null
duplicate_of: null
---
Low. src/metabrowser/cache/acquire.py:256 still says 'over its size limit'. PR 768, review https://github.com/jlevy/metabrowser/pull/768#pullrequestreview-6031209981
