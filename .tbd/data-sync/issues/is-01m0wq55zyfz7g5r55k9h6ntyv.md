---
type: is
id: is-01m0wq55zyfz7g5r55k9h6ntyv
title: Make Git commit rows follow the nav-list arrow-key contract
kind: bug
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T15:03:26.461Z
updated_at: 2026-08-25T15:04:22.128Z
---
Finding source: user acceptance testing on the active PR. Files/functions: src/metabrowser/static/git-panel.js renderPanel, appendRows, renderRow, selectCommit, and new focused-row helpers; tests/dom/git-panel-behavior.js fake focus/event support and row-keyboard cases; docs/design-system.md shared nav-like row keyboard contract; tests/test_design_vocabulary.py enforcement registry; docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md goal and implementation phase. Behavior/invariants: a Git history row set has one roving tab stop; unmodified ArrowUp and ArrowDown move focus to the adjacent mounted commit and open it through selectCommit; movement clamps at the first and last row without reopening; click, Enter, Space, pointer/focus preparation, pagination, stale-selection safety, and direct routes remain unchanged. Acceptance: focused failing test first; rows expose one tab stop; arrow movement prevents browser scrolling, focuses and selects the destination, allows repeat, and clamps at boundaries; the design-system rule is documented and statically tied to both the file tree and Git history; focused browser tests, make format, make verify, real-browser trading-repo smoke, push, PR disposition, and CI pass.
