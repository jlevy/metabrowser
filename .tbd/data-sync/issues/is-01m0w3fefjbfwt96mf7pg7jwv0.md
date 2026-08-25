---
type: is
id: is-01m0w3fefjbfwt96mf7pg7jwv0
title: "PR #74 scope audit S12: reject mixed-identity and nonmonotonic provider batches"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:19:31.313Z
updated_at: 2026-08-25T09:57:01.027Z
closed_at: 2026-08-25T09:57:01.027Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
InventoryCoordinator._publish_provider_batches validated only the merged latest ChangeBatch. Earlier coalesced batches could carry another fingerprint or a non-increasing cursor and still contribute dirtiness/work. Validate every batch against the opened identity and require strictly increasing sequences before merge; add coordinator failure-path coverage. Evidence: src/metabrowser/inventory_engine/coordinator.py _publish_provider_batches and _merge_provider_batches.
