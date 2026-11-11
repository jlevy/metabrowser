---
type: is
id: is-01m74vxbr4c185rat4dnj8bhv6
title: "PR #347 A14: prepare_pull_comparison is dead code in this layer"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:39.491Z
updated_at: 2026-11-11T09:41:54.298Z
closed_at: 2026-11-11T09:41:54.297Z
close_reason: "declined: prepare_pull_comparison stays because #348 edits it in place and adds its caller in the same atomic stack merge; now tested here"
resolution: null
duplicate_of: null
---
Severity: Low. PR #347 review A round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855504972). References: pulls.py:882-903.
