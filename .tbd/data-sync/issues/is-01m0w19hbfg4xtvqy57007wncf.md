---
type: is
id: is-01m0w19hbfg4xtvqy57007wncf
title: "Phase 4.3: Cache changed-run refinements in the shared render model"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0w19z4e4ze02hwv6m24zvqv
parent_id: is-01m0w18bwddnc94htabvg4zke8
created_at: 2026-08-25T08:41:20.493Z
updated_at: 2026-08-25T08:41:34.605Z
---
Files/functions:
- Extend src/metabrowser/builtin_plugins/diff/diff-render-model.js types with ChangedRunRefinement, per-line old/new intraline ranges, and per-hunk cached split rows.
- Add refineHunkChangedRuns(hunk, budget) and refineFileChangedRuns(model, budget, signal) using refineChangedRun from diff-intraline.js.
- Extend tests/dom/diff-syntax-behavior.js or a focused render-model behavior suite and register it in tests/test_diff_browser_js.py.

Behavior/invariants:
- Collect each contiguous changedRun without reordering; translate algorithm indices back to the hunk records and cache one semantic row model shared by unified/split renderers.
- Plain/timed_out/over_budget/error results retain positional split rows, empty intraline ranges, exact text, and whole-line treatment.
- Intraline refinement never computes syntax and syntax never computes refinement.
- Abort between runs/files and contain a refinement failure to one changed run.

TDD/acceptance:
- Begin with failing tests for cached monotonic shifted/unequal alignment, per-line range assignment, positional fallback, independent syntax state, repeated-call idempotence, and abort containment.
- Focused model, syntax, and diff behavior tests pass.
- No view/CSS work or wire-schema changes in this bead.
