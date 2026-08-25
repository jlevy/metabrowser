---
type: is
id: is-01m0w19z4e4ze02hwv6m24zvqv
title: "Phase 4.4: Compose syntax and intraline rendering in unified and split layouts"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0w1a9mspr5zknta7jg40j3n
  - type: blocks
    target: is-01m0w1ane5z1tkemm258pkpq60
parent_id: is-01m0w18bwddnc94htabvg4zke8
created_at: 2026-08-25T08:41:34.605Z
updated_at: 2026-08-25T09:14:53.677Z
closed_at: 2026-08-25T09:14:53.676Z
close_reason: Unified and split now compose cached syntax and intraline boundaries through exact text nodes, share refined alignment, and preserve first paint, fold/layout state, hydration, generation, abort, replacement, and disposal paths; focused DOM tests and real-app layout checks pass.
resolution: null
duplicate_of: null
---
Files/functions:
- Update src/metabrowser/builtin_plugins/diff/diff-view.js imports/types/state from syntax to renderModel.
- Add composeTextRuns(text, tokenRuns, intralineRanges), update renderTextHost/appendTokenRuns, and attach semantic inner-change classes with text nodes only.
- Replace pairChangedRun/projectSplitHunk positional ownership with cached model rows.
- Extend the progressive queue (rename syntaxTail/yieldForSyntax as appropriate) so refineFileChangedRuns settles before highlightFileSyntax per file.
- Update enhance, reprojectFile, layout switching, hydration/replacement, generation guards, abort, timers/yielders, and disposal paths.
- Extend tests/dom/diff-view-behavior.js and tests/dom/diff-syntax-behavior.js.

Behavior/invariants:
- Intersect syntax-token and intraline boundaries without losing/duplicating UTF-16 text; syntax foreground classes and inner-background class can coexist.
- Unified order remains server order; split uses cached monotonic rows and empty cells.
- First paint is complete plain text. Unified refinement updates existing hosts where alignment permits; split alignment change reprojects only its file.
- Preserve expanded folds, layout preference, mount/layout generations, deferred hydration, rapid layout switches, replacement, and disposal with no late mutation.
- Any algorithm or syntax failure degrades independently.

TDD/acceptance:
- Failing tests cover exact text and unsafe text-node construction, overlapping token/range boundaries, improved shifted alignment, unified source order, fold persistence, immediate layout switches, deferred hydration, replacement, abort, and disposal.
- Focused DOM suites and strict check-JS pass.
- Scope excludes final colors and performance policy.
