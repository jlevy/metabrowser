---
type: is
id: is-01m0w40rak3wfpqh9cywg1sxcm
title: S17 Remove unsupported special-object contract kind
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:28:58.450Z
updated_at: 2026-08-25T09:57:01.050Z
closed_at: 2026-08-25T09:57:01.050Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
The provider contract advertises EntryType.OTHER, but the Python walker classifies every non-directory/non-symlink object as a regular file, _internal_entry rejects OTHER, and events_route cannot serialize it. This is an unsupported speculative axis in a functionality-preserving refactor. Remove OTHER from the Phase 1 contract and narrow maintained docs/tests to the three representable kinds; keep any future special-object wire extension as separately measured work.
