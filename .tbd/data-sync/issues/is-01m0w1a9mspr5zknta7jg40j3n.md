---
type: is
id: is-01m0w1a9mspr5zknta7jg40j3n
title: "Phase 4.5: Settle semantic intraline colors and contrast coverage"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0w1ane5z1tkemm258pkpq60
parent_id: is-01m0w18bwddnc94htabvg4zke8
created_at: 2026-08-25T08:41:45.369Z
updated_at: 2026-08-25T08:41:57.444Z
---
Files/functions:
- Add semantic custom properties in src/metabrowser/builtin_plugins/diff/styles.css for ordinary add/delete rows, lighter refined replacement rows, and stronger old/new inner changed ranges.
- Apply refined-row and inner-range classes emitted by diff-view.js without changing syntax foreground ownership.
- Extend tests/test_syntax_palette.py contrast calculations for context, ordinary add/delete, refined add/delete, and inner-change backgrounds across light, dark, and supported high-contrast themes.
- Extend DOM assertions for class/layer structure.

Behavior/invariants:
- Pure additions/deletions and unrelated replacements retain the current 12% whole-line status mix.
- Similar paired replacements use visibly lighter row backgrounds plus stronger changed-range backgrounds.
- All colors come from shared semantic design tokens; no local literal palette.
- Line numbers and +/- markers remain non-color indicators; selection, focus, and syntax foregrounds remain readable.

TDD/acceptance:
- Add failing palette and DOM assertions before styles.
- Record the chosen mix values and contrast results in the relevant exploration/plan evidence if numerical reasoning is needed.
- Light, dark, high-contrast palette tests and focused browser CSS assertions pass.
