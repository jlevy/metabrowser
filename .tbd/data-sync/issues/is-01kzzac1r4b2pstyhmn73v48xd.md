---
type: is
id: is-01kzzac1r4b2pstyhmn73v48xd
title: "PR #40 review R6: eliminate duplicate registry matching in rollups"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:01.475Z
updated_at: 2026-08-14T05:25:17.216Z
closed_at: 2026-08-14T05:25:17.215Z
close_reason: "Fixed: one shared rollup partition classifies every distinct logical extension once and feeds both modern and compatibility projections."
---
PR #40 comment 5289663054, R6. Breakdown and legacy type tallies repeat suffix matching over identical extension keys. Remove unreachable serialization or share/memoize matches, with performance-sensitive regression coverage.
