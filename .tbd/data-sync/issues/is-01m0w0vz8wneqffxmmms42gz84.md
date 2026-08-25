---
type: is
id: is-01m0w0vz8wneqffxmmms42gz84
title: "PR #74 scope audit S7: make refresh completion observable without transactional overclaim"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:33:55.994Z
updated_at: 2026-08-25T09:57:01.003Z
closed_at: 2026-08-25T09:57:01.003Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
The architecture promises one atomic provider refresh and one resulting cursor, but RefreshReceipt carries no observation boundary and the Python provider commits valid observations separately. Define the minimal useful guarantee: one bounded refresh call returns a terminal EngineVersion after all accepted observations have been incorporated; do not require filesystem hints to become a fictitious transaction. Update contract, coordinator/provider tests, docs, and the FDU adoption gate.
