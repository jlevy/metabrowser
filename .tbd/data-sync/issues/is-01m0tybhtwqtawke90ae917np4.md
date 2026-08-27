---
type: is
id: is-01m0tybhtwqtawke90ae917np4
title: Align unreleased notes with exact-main evidence and aggregate intermediate fixes
kind: chore
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0vcqjmdqs2zhk804rgbjjm9
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-24T22:30:46.363Z
updated_at: 2026-08-27T00:43:36.007Z
closed_at: 2026-08-27T00:43:36.007Z
close_reason: The changelog and performance ledger now use the refreshed exact v0.8.0 candidate evidence, preserve full ranges, and aggregate intermediate fixes into released outcomes.
resolution: null
duplicate_of: null
---
Release-readiness finding on main c123ae6. CHANGELOG Unreleased calls exp-014 values from candidate bf7771b the final installed wheel, but the exact merged-main validation is exp-015 at bae51fd and reports different backend, paint, request, and transfer values. The ensureKindAssets entry also records an Overview failure introduced and corrected inside this unreleased performance cycle. Update claims to the exact-main experiment and fold that intermediate failure into the on-demand-loading outcome.
