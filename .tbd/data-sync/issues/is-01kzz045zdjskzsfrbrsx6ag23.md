---
type: is
id: is-01kzz045zdjskzsfrbrsx6ag23
title: Add bounded No extension and Remaining types children
kind: feature
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - rollup
  - cardinality
dependencies:
  - type: blocks
    target: is-01kzz04wegtbq1pxpq9ser4wj3
  - type: blocks
    target: is-01kzz05ksdr74fcztg1rpmj13p
  - type: blocks
    target: is-01kzz05x3x3d6y2n9gzeq8xmqg
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:02:57.900Z
updated_at: 2026-08-14T03:33:59.039Z
closed_at: 2026-08-14T02:48:42.957Z
close_reason: Added independently capped 20-item No extension and Remaining types children with deterministic dual-population ranking and exact Others conservation.
---
Extend subtree aggregates with exact no-extension basename and remaining logical-extension counters for all/unignored file and byte populations. Implement one reusable aggregate-before-bound ranking over every required population, cap each special parent at 20 children, and emit an exact Others row with omitted_distinct_values. Add named query/settings limits while retaining type_top compatibility. Tests: limits 0/1/19/20/21, count-heavy and byte-heavy values, importance visible only in unignored scope, deterministic ties, exact Others, high-cardinality response bounds, and live updates. Acceptance: special parents conserve exactly and no unbounded name list crosses the wire.
