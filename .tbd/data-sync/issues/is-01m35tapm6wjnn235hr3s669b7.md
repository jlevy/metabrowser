---
type: is
id: is-01m35tapm6wjnn235hr3s669b7
title: Execute v0.12 direct-PR alpha acceptance on installed artifacts and a real browser
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-23T00:23:26.596Z
updated_at: 2026-09-23T01:38:18.719Z
started_at: 2026-09-23T01:37:28.312Z
---
Run T1 and T2 acceptance from the alpha test plan after the corresponding implementation/publication beads complete. Exercise the installed wheel through real CLI and HTTP startup, GitHub repository/tree/blob/commit/raw/PR URL forms, a directly addressed PR absent from the index, cold/warm/offline behavior, two concurrent revisions, private authorization and typed failures, trust with populated cache, and browser navigation/rendering. Add deterministic adapter-to-store-to-view and production-JS golden coverage in each owning implementation PR; record exact head/base/main/tool versions and pass/fail/blocked for manual rows M01-M11, including M10b explicit provider rebind. T0 was exercised during mb-eegt but does not satisfy this future GitHub alpha. Keep the whole formal stack held until stabilization; this task does not merge or publish a release. No tbd release or optional shortcut cleanup gates these tests.

## Notes

The walkthrough now explicitly exercises binding a disposable checkout, changing its remote, rejecting automatic identity reassignment, and using the planned explicit rebind operation without presenting old snapshots as new content. Feature implementation remains open; this tracking edit is not execution of T1/T2 acceptance.
