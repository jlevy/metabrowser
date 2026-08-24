---
type: is
id: is-01m0tyg1dzdb1cmytsxd1v02dk
title: "PR #76 review R2: record renderer candidate evidence"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
  - review
dependencies: []
parent_id: is-01m0txbdd0b5cyzcp64vsje7kp
created_at: 2026-08-24T22:33:13.406Z
updated_at: 2026-08-24T22:41:50.712Z
closed_at: 2026-08-24T22:41:50.710Z
close_reason: "Fixed in reviewed design revision 5604e04; disposition published on PR #76."
resolution: null
duplicate_of: null
---
PR #76 review R2 (Medium), parent plan Phase 3 and focused plan product review. Record why @pierre/diffs and @git-diff-view/core are not adopted for syntax/split: both require runtime dependencies and bundling, while their main value remains in deferred intraline, virtualization, and worker work. Preserve the measured gate for those later features.
