---
type: is
id: is-01m00nzbe12ws4pm4870qgr3q1
title: Folder rollup overview and treemap improvements
kind: epic
status: closed
priority: 2
version: 14
labels:
  - browser
dependencies: []
child_order_hints:
  - is-01m00q71z9swgdwtktedqc95k3
  - is-01m00nzbv28s9cd2qjykjfdp8w
  - is-01m00phrnxt0gptpykhzwy1s36
  - is-01m00pkn2tv46k3cr95z8m81v6
  - is-01m00phs4p1dvrzhgay8fqvwwr
  - is-01m00prc3fp6xsnkj84t27rfcf
  - is-01m00px2azd2vq64p7w4cas7r2
  - is-01m00prch1akzeds6rnwc4rkwy
  - is-01m00q31dkqwp66dvmy7qjnq7h
created_at: 2026-08-14T17:44:02.752Z
updated_at: 2026-08-14T19:02:48.484Z
closed_at: 2026-08-14T19:02:48.483Z
close_reason: All child behavior, design-system, data-model, documentation, TDD coverage, and full repository validation are complete.
---
Unify the correctness, controls, hierarchy, bounded disclosure behavior, ordering, totals context, and loading presentation of folder rollup views.

The epic covers the overview File Totals and File Types sections, treemap context and controls, shared design-system primitives, complete-snapshot rendering, metric-aware ranking, and the File Rollup Format support needed for safe expandable subsections. Each child bead owns one independently testable concern and the dependency graph records the implementation order.
