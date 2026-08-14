---
type: is
id: is-01kzz03xc66nzafcd0dn48zger
title: Build the conserved hierarchical file-type breakdown
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - rollup
  - python
dependencies:
  - type: blocks
    target: is-01kzz045zdjskzsfrbrsx6ag23
  - type: blocks
    target: is-01kzz04fp7330jyn2h03m635qc
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:02:49.093Z
updated_at: 2026-08-14T02:03:07.846Z
---
Replace tuple-oriented semantic serialization in inventory_rollup.py and wire_models.py with typed FileTypeMeasure, population, group, family, extension, fallback, Others, and FileTypeBreakdown models. Aggregate the complete subtree before presentation bounds; emit all/unignored files and apparent bytes; nest nonempty groups and complete family children; preserve exact root and parent conservation; and include registry identity. Retain legacy type_tallies/ext_tallies during one additive transition. Tests: empty, ignored-only, zero-byte, truncated, live add/change/remove, group ordering, every conservation equation, cold envelopes, and additive wire compatibility. Acceptance: file-type-breakdown-v1 is produced from one registry/classifier path with no renderer-specific aggregation.
