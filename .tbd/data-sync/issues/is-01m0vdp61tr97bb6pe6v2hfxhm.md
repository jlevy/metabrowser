---
type: is
id: is-01m0vdp61tr97bb6pe6v2hfxhm
title: "PR #74 review R6: enforce provider boundary invariants"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:43.384Z
updated_at: 2026-08-25T04:46:35.877Z
closed_at: 2026-08-25T04:46:35.876Z
close_reason: R6 resolved and verified by make verify.
resolution: null
duplicate_of: null
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R6 Medium. contract.py:839-849 accepts duplicate priority paths and path-bearing contract records lack one canonical POSIX-relative validation rule. Centralize validation and extend the provider contract harness.

## Notes

Centralized canonical POSIX-relative path validation and applied it to entries, queries, catalog records, issues, recent ignored directories, change batches, observations, receipts, priority requests, and the overlay. Added identity, receipt, uniqueness, bounds, runtime configuration, and continuation invariants plus contract-harness coverage.
