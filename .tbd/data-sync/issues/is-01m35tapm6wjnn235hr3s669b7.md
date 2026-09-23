---
type: is
id: is-01m35tapm6wjnn235hr3s669b7
title: Execute v0.12 direct-PR alpha acceptance on installed artifacts and a real browser
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-23T00:23:26.596Z
updated_at: 2026-09-23T00:23:26.596Z
---
Run T1 and T2 acceptance from the alpha test plan after the corresponding implementation/publication beads complete. Exercise the installed wheel through real CLI and HTTP startup, GitHub repository/tree/blob/commit/raw/PR URL forms, a directly addressed PR absent from the index, cold/warm/offline behavior, two concurrent revisions, private authorization and typed failures, trust with populated cache, and browser navigation/rendering. Add deterministic adapter-to-store-to-view and production-JS golden coverage in each owning implementation PR; record exact head/base/main/tool versions and pass/fail/blocked for manual rows M01-M11. T0 was exercised during mb-eegt but does not satisfy this future GitHub alpha. Keep the whole formal stack held until stabilization; this task does not merge or publish a release.
