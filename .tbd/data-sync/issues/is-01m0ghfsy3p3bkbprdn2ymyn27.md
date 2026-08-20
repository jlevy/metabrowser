---
type: is
id: is-01m0ghfsy3p3bkbprdn2ymyn27
title: Age styling is one vocabulary everywhere it appears
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-20T21:33:29.922Z
updated_at: 2026-08-20T21:33:29.922Z
---
Relative ages in the git panel do not match the file tree's age styling. An age is an age: one size, one color, one abbreviation rule, unless the design system states an explicit exception. Define Age as a vocabulary element in design-system.md, apply it to the tree rows, the git graph rows, and the commit detail, and pin it in tests/test_design_vocabulary.py.
