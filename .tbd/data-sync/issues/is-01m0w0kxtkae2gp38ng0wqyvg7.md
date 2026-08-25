---
type: is
id: is-01m0w0kxtkae2gp38ng0wqyvg7
title: "PR #74 scope audit S6: bound lifecycle issue payloads"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:29:32.370Z
updated_at: 2026-08-25T08:29:32.370Z
---
IndexState is returned by every read and change, but its issues tuple and detail strings are currently unbounded, leaving an unbounded FFI result outside the query row limits. Add explicit cardinality and detail-size bounds with construction tests and document provider-side summarization beyond the cap; carry the same gate to FDU.
