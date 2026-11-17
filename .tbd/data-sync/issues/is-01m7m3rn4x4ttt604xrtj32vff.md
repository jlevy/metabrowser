---
type: is
id: is-01m7m3rn4x4ttt604xrtj32vff
title: "CI speed 1.6: finish Phase 1's 10-run acceptance on #499 (7 more CI attempts), and decide the unit split from the full sample"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T06:40:30.364Z
updated_at: 2026-11-17T08:28:36.701Z
---
The plan's Testing Strategy asks for 10 runs of the pull request for the xdist row, the admitted-git row, and the concurrent goldens. #499 (CI run 44026747033 at d5a05e20) has three green attempts: the parallel tier ran 2.0 to 2.4 times faster than one process (bar 2.3), with up to 54 percent run-to-run variation, recorded in plan section Phase 1 Measurements. Rerun until 10 green attempts or a failure that a serial run does not have; append the numbers to Phase 1 Measurements. If the median factor stays under 2.3, Phase 2 (mb-oz36) splits unit in two with SHARD=I/2 from the start. Optional measurement: PYTEST_WORKERS above 4, since the tests spawn Git, Node, and metab processes and each ran 1.1 to 1.8 times slower beside the others.

## Notes

2026-11-17: five green runs now (44026747033 x3, 44041121764, 44043995823); factor 2.0/2.2/2.2/2.2 on 3.12/3.13/3.14/3.14t, recorded in Phase 1 Measurements at 919cb1c0. Five more runs remain for the plan's 10.
