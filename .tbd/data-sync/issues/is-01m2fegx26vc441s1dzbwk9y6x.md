---
type: is
id: is-01m2fegx26vc441s1dzbwk9y6x
title: Baseline-align the Git commit summary metadata without growing the line
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-09-14T07:53:49.381Z
updated_at: 2026-09-14T07:53:49.381Z
---
Found while addressing PR #118 review R1. .git-commit-meta sets the --nav-font-size monospace revision beside --body-font-size sans author and age in an align-items: center row; their baselines differ by 0.25px (DPR 2) to 0.75px (DPR 1). Opting .git-commit-identity/.git-commit-author/.git-commit-age into align-self: baseline zeroes that but grows the line from 21 to 22.25px at DPR 2, because the mono and sans line boxes extend differently around the baseline. docs/design-system.md 'Row Text Shares a Baseline' records it as the deliberate exception; resolve the line-box mismatch, then add the row to the table and to tests/test_design_vocabulary.py::_baseline_rows.
