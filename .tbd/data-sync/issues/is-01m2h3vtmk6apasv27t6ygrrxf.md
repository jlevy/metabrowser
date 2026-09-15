---
type: is
id: is-01m2h3vtmk6apasv27t6ygrrxf
title: "GitHub Phase 3: selected PR and index cache slices"
kind: feature
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01m10xd666fefs5z7ft5m58zj0
child_order_hints:
  - is-01m2h7h50h2y8hhhq7x7f1zcmd
  - is-01m2h7hrjfx06hzpr7ptz7k9wn
created_at: 2026-09-14T23:26:01.873Z
updated_at: 2026-09-15T00:31:44.295Z
---
Umbrella for two additive provider-cache deliveries. First, mb-h64t hydrates one directly addressed PR bundle and selected refs without requiring an index. Then mb-lnkl adds a bounded repository-scoped ChangeRequestIndex discovery cache whose list rows fetch no Git refs. Both publish immutable provider-neutral Hosted Review Format snapshots, manifests, and atomic current pointers; expose completeness, freshness, typed failures, and offline reuse; and never retain raw API responses or credentials.
