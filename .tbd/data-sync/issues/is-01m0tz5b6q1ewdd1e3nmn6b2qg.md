---
type: is
id: is-01m0tz5b6q1ewdd1e3nmn6b2qg
title: "Step 3: Render progressively highlighted unified diffs"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tw8haj67tstjassnq9we07
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T22:44:51.542Z
updated_at: 2026-08-24T22:45:01.678Z
---
Files and functions: refactor src/metabrowser/builtin_plugins/diff/diff-view.js around createFileState, renderFileBody, renderUnifiedHunk, renderUnifiedLine, and appendTokenRuns; consume buildHunkRecords/highlightHunkSides from diff-syntax.js; extend tests/dom/diff-view-behavior.js and tests/test_diff_browser_js.py. Behavior: mount all ready hunks as readable textContent first, then replace only current text hosts with createElement-created hljs token spans from cached runs; deletions use old tokens, additions and unified context use new tokens. Invariants: row background remains the only diff status background, exact text/numbers/markers/no-newline state remain unchanged, shell pre code:not(.hljs) cannot select token hosts, syntax failure is a no-op, and re-rendering uses cached semantic/token state without re-lexing. TDD acceptance: focused fake-DOM tests prove plain-first rendering, side-token choice, safe span construction, no double highlight surface, failed enhancement fallback, and unchanged existing disclosure/fold/availability behavior.
