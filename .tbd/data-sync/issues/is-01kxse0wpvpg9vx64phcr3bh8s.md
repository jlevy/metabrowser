---
type: is
id: is-01kxse0wpvpg9vx64phcr3bh8s
title: "Diff P3: multi-file review surface and renderer library decision gate"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:59.931Z
updated_at: 2026-11-20T19:15:57.701Z
extensions: {}
---
Review-surface follow-ups and the renderer library decision gate. The multi-file surface exists: a commit's comparison in the Commits tab and a pull request's Changes tab mount one diff view with sticky file bars, deferred per-file hydration, and go-to-file (#284). Remaining: keyboard next-file and next-hunk navigation; local viewed state; the pinned spike of @pierre/diffs (stable + CodeView) against @git-diff-view/core, scored on bundle size, CSP and worker behavior from plugin-static, dependency count, and benchmarks, with the decision to adopt one or recommit to the in-house renderer recorded in the spec (Phase 3); and the Files-tree change-decoration decision.
