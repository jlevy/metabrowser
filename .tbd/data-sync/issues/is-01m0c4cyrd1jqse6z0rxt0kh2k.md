---
type: is
id: is-01m0c4cyrd1jqse6z0rxt0kh2k
title: "static/diff_model.js: the browser model, same corpus"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4cz2kcc5e7em60dn3jya4
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:47.340Z
updated_at: 2026-08-19T04:28:17.196Z
---
parseManifest, parseFilePatch, fileChangeLabel(change) for the indicator set (renames with old path and folder moves, copies, mode changes, type changes, binary), and validateDocument. Runs the same conformance corpus as the Python side, which is what keeps the two from drifting.
