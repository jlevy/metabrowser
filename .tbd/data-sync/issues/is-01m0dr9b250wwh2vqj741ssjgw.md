---
type: is
id: is-01m0dr9b250wwh2vqj741ssjgw
title: "Decide: combined (merge) diff representation"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T19:34:34.820Z
updated_at: 2026-11-14T18:47:05.860Z
---
The format compares exactly two snapshots; merges are viewed against first-parent by policy, and the parser now marks combined-diff input unsupported instead of misparsing. Decide whether N-parent combined diffs ever get first-class representation (an N-snapshot comparison variant, or per-parent comparison tabs over the same commit), or whether first-parent + per-parent tabs is the standing answer. Record the decision in diff-sources-and-anchoring.md; git's own docs mark combined diffs as display-only (not meant to be applied), which argues for per-parent comparisons.
