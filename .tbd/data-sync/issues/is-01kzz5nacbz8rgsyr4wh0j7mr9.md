---
type: is
id: is-01kzz5nacbz8rgsyr4wh0j7mr9
title: Preserve legacy rollup type_top overrides in the SDK
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - file-types
  - review
dependencies: []
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T03:39:42.346Z
updated_at: 2026-08-14T03:39:47.278Z
closed_at: 2026-08-14T03:39:47.277Z
close_reason: SDK now resolves legacy and modern rollup limits before serializing both aliases, with behavioral tests for legacy and modern caller overrides.
---
Coordinate type_top and remaining_top query serialization so legacy callers override defaults and modern callers remain compatible with old servers. Add behavioral regressions.
