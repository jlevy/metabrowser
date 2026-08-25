---
type: is
id: is-01m0w0kxtkae2gp38ng0wqyvg7
title: "PR #74 scope audit S6: bound lifecycle issue payloads"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:29:32.370Z
updated_at: 2026-08-25T09:57:00.997Z
closed_at: 2026-08-25T09:57:00.997Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
IndexState is returned by every read and change, but its issues tuple and detail strings are currently unbounded, leaving an unbounded FFI result outside the query row limits. Add explicit cardinality and detail-size bounds with construction tests and document provider-side summarization beyond the cap; carry the same gate to FDU.
