---
type: is
id: is-01m2h84aknesxkkk8kdt75tc5s
title: Root /api/tree server time is 3-44x v0.9.1 during a walk on a repository-shaped tree
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-09-15T00:40:34.677Z
updated_at: 2026-09-15T00:40:34.677Z
---
exp-034, quiet 4-CPU host, project-10 (118,860 walker-visible files), five back-to-back headed browser pairs, v0.9.1 wheel against main 03fd7997. The root /api/tree fetch's Server-Timing (tree_fetch_srv_ms) is 1, 1, 3, 3, 1 ms on the control and 10, 44, 9, 42, 39 ms on the candidate: every pair exceeds the release's 1.3x rule. load_tree_ms, the same fetch plus its render, follows: 16-28 ms against 22-69 ms.

exp-033 saw the same shape under load (1-9 ms -> 12-68 ms) and attributed it to the provider read moving into asyncio.to_thread. The architecture document states the mechanism directly: 'A provider read through the coordinator is eight loop iterations and a worker hop, so it pays that wait eight times', against a 5 ms interpreter switch interval while the walker holds the GIL in bounded slices (docs/project/architecture/arch-python-inventory-cost.md, Passes That Overlap the Walk). Eight hops at up to 5 ms is the 9-44 ms observed.

Absolute cost is small and inside every gate: the candidate still reaches first rows in 198-317 ms against the control's 1,189-1,392 ms, so this is a ratio regression on a metric whose absolute value the release improves overall. Recorded in exp-034 as an explained, accepted difference rather than a silent one.

Fix direction: fewer loop hops per read, or a read path that does not cross the coordinator once per hop while a walk is running. Measure with run.py probe-server, which samples the route across the scan rather than drawing one sample.
