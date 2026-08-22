---
type: is
id: is-01m0m5vwhzn3h5bxyy79w3st82
title: Persist the index across runs and revalidate on start (H21)
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T07:27:20.634Z
updated_at: 2026-08-22T07:27:20.634Z
---
Revisits the plan's non-goal, which deferred this 'until the progressive path exists' — it now exists (partial-state serving, tally_cache_status=scanning labels). Persist at walk end, load on start, serve stale-labeled instantly, revalidate in background (mtime per directory). fdu proved snapshot+revalidate. Biggest lever at large N: 1M revisit from tens of seconds to sub-second. Needs a format decision measured for load cost.
