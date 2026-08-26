---
type: is
id: is-01m0y5hvk0rrcn98h6rv5d7dje
title: "Phase 4.8.2: Test and implement pale rows, strong intraline spans, and gutter bars"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0y5hvxah44e9kdbnmpq97hs
parent_id: is-01m0y5h1kk1waq5baqsvmqcx6k
created_at: 2026-08-26T04:34:16.287Z
updated_at: 2026-08-26T04:37:07.199Z
---
Files/functions:
- Update tests/test_syntax_palette.py constants plus test_syntax_foregrounds_meet_contrast_over_diff_tints and test_diff_syntax_hosts_and_split_geometry_keep_the_css_contract.
- Update src/metabrowser/builtin_plugins/diff/styles.css host tokens and selectors for .diff-line-add, .diff-line-del, .diff-intraline-change, and the first .diff-line-number child.
- Update tests/dom/diff-view-behavior.js only if existing unified/split row-class assertions do not prove selector coverage.

Behavior/invariants:
- Ordinary and refined changed rows use the same pale add/delete fill.
- Refined changed spans have a materially stronger effective fill than their row.
- Every add/delete row in unified and every add/delete side in split has a solid leading status-colored inset on its first number cell.
- The inset changes no grid column, box geometry, text alignment, DOM, or main-thread work.
- Syntax foregrounds retain >=4.5:1 contrast in light and dark themes.

TDD/acceptance:
- Write failing palette/CSS contract assertions first, confirm failure, then implement.
- Focused Python and DOM browser tests pass and exact text/syntax composition remains unchanged.
