---
type: is
id: is-01m0c4cyrd1jqse6z0rxt0kh2k
title: "static/diff_model.js: the browser model, same corpus"
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4cz2kcc5e7em60dn3jya4
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:47.340Z
updated_at: 2026-08-19T16:19:41.577Z
closed_at: 2026-08-19T16:19:41.576Z
close_reason: "Landed as builtin_plugins/diff/diff_model.js (plugin-local rather than static/: one consumer today; promoting to a shared core module when a second consumer exists follows the git-graph plan's own one-consumer rule). Full corpus runs through it in tests/dom/diff_model_behavior.js."
---
parseManifest, parseFilePatch, fileChangeLabel(change) for the indicator set (renames with old path and folder moves, copies, mode changes, type changes, binary), and validateDocument. Runs the same conformance corpus as the Python side, which is what keeps the two from drifting.
