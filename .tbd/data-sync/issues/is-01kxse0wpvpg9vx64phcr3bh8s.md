---
type: is
id: is-01kxse0wpvpg9vx64phcr3bh8s
title: "Diff P3: multi-file review surface and renderer library decision gate"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-07-18-git-diff-view.md
labels:
  - diff
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:59.931Z
updated_at: 2026-08-16T08:06:30.382Z
extensions:
  linear:
    id: 1f7bf3e6-0c7f-4a6e-b747-082187c56ecd
    linked_at: 2026-08-16T08:06:30.382Z
---
Full-pane review surface: one scroll owner, sticky headers, keyboard nav, local viewed state, adaptive mounting with virtualization only above measured thresholds. Pinned spike of @pierre/diffs (stable + CodeView) vs @git-diff-view/core scored on bundle size, CSP/worker behavior from plugin-static, dependency count, benchmarks; adopt or recommit to custom renderer. Decide Files-tree change decorations.
