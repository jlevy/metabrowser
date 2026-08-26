---
type: is
id: is-01m0ycs63s5tm53hqjw2xraw1m
title: Correct pure-line and intraline diff fill hierarchy
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0y5h1kk1waq5baqsvmqcx6k
created_at: 2026-08-26T06:40:36.472Z
updated_at: 2026-08-26T07:43:11.545Z
closed_at: 2026-08-26T07:43:11.544Z
close_reason: "Implemented the design-system diff hierarchy: strong semantic fills for pure additions/deletions, pale unchanged portions only on refined pairs, strong intraline spans, and semantic gutter bars. Exact globally installed 4d45e0d opens the representative commit in Split with 119 pure additions, 8 pure deletions, 357 refined rows, and 219 intraline spans; focused palette/design tests and make verify pass."
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/builtin_plugins/diff/styles.css semantic diff tokens and .diff-line-add/.diff-line-del/.diff-line-refined/.diff-intraline-change rules; tests/test_syntax_palette.py palette, selector, and contrast contracts; tests/dom/diff-view-behavior.js refined versus unrefined row-class coverage if needed; docs/design-system.md Diff Change Hierarchy; docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md Phase 4.8 follow-up; CHANGELOG.md. Behavior/invariants: a wholly added or deleted unrefined line uses the stronger success/error background; a paired line with intraline refinement uses a pale row background for unchanged text and the stronger background only on changed spans; every changed row retains its solid semantic gutter; unified and split share the same classes and hierarchy; syntax foregrounds retain at least 4.5:1 contrast in both themes; no DOM, JavaScript, dependency, schema, or compatibility cost. Acceptance: focused static/DOM tests distinguish unrefined strong rows from refined pale rows plus strong spans, preserve gutter and contrast contracts, and make format/make verify plus real-browser light/dark unified/split checks pass.
