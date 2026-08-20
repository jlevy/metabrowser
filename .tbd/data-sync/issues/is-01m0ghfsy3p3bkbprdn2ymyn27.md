---
type: is
id: is-01m0ghfsy3p3bkbprdn2ymyn27
title: Age styling is one vocabulary everywhere it appears
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T21:33:29.922Z
updated_at: 2026-08-20T21:47:43.559Z
closed_at: 2026-08-20T21:47:43.559Z
close_reason: "Landed in d84e934: MetabrowserFormatters.age is the one primitive; tree, graph rows, and commit detail all use it; the tier rule owns hue/weight/size/numerals; documented as Age and pinned in test_design_vocabulary."
---
Relative ages in the git panel do not match the file tree's age styling. An age is an age: one size, one color, one abbreviation rule, unless the design system states an explicit exception. Define Age as a vocabulary element in design-system.md, apply it to the tree rows, the git graph rows, and the commit detail, and pin it in tests/test_design_vocabulary.py.
