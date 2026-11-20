---
type: is
id: is-01m7h20d904hvcrfctdk364men
title: "PR #449 B5: the route-pairs instrument times only part of what H116 changes"
kind: bug
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-16T02:12:03.999Z
updated_at: 2026-11-20T17:24:09.984Z
---
Deferred from review B of PR #449 (B5, https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914053530). The README part landed in 12167dfe3 (what the pairs cannot see; counts by Git version and driver configuration). Remaining, for explorations/performance-loop/git-route-pairs.mjs before exp-096's first pair: record each server's git --version and whether the served folder's configuration names a textconv driver (or diff.submodule=diff); add an option for a comparison's single-file ask (file=), B1's worst case; optionally a concurrent probe timing a small route while a large comparison is in flight. Waits on the registration of H116's timed round (exp-096).
