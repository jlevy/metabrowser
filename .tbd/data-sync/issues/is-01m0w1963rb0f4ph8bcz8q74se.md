---
type: is
id: is-01m0w1963rb0f4ph8bcz8q74se
title: "Phase 4.2: Extract the syntax-neutral diff render model"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0w19hbfg4xtvqy57007wncf
parent_id: is-01m0w18bwddnc94htabvg4zke8
created_at: 2026-08-25T08:41:08.983Z
updated_at: 2026-08-25T08:43:56.677Z
---
Files/functions:
- Add src/metabrowser/builtin_plugins/diff/diff-render-model.js.
- Move DiffLineRecord/DiffHunkRecord model types, buildHunkRecords, side numbering, changed-run assignment, and source-stream construction out of diff-syntax.js.
- Rename buildFileSyntaxModel to buildFileRenderModel and update co-shipped imports/call sites in diff-view.js and tests/dom/diff-syntax-behavior.js.
- Keep languageForSide, syntaxInputBytes, applySideTokens, and highlightFileSyntax in diff-syntax.js.

Behavior/invariants:
- This is an internal co-shipped contract change; update every consumer together and add no compatibility alias.
- Source order, line numbers, changedRun identity, old/new stream text, byte caching, and existing syntax behavior remain unchanged.
- Syntax ownership becomes strictly token/language/measurement only and does not depend on intraline computation.

TDD/acceptance:
- Update focused model/syntax behavior tests first so the removed export fails, then complete the extraction.
- Existing diff view and syntax suites pass with no manifest/loading-tier change because imported modules are on demand with the diff plugin.
- Scope is one coherent ownership/refactor commit independent of the algorithm bead.
