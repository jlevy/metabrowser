---
type: is
id: is-01m0fvhd6kc6k47rpvnx7cgs3r
title: "Design system: one disclosure motion primitive on every toggle"
kind: feature
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T15:09:53.733Z
updated_at: 2026-08-20T15:28:42.004Z
closed_at: 2026-08-20T15:28:41.991Z
close_reason: "Landed in 4554983: one height-travel recipe on var(--transition-fast) across tree folders, containers, diff sections, folds, and Overview panels; class-driven collapse throughout; reduced-motion honored; vocabulary-test enforced"
---
A standard smooth, short expand/collapse travel, consistent everywhere: one primitive (height auto<->0 via scoped interpolate-size, visibility swap, overflow hidden) on var(--transition-fast) so body travel and chevron rotation share one duration. Apply to diff file sections, diff fold groups, tree folder children, tree container children, and folder Overview panels; reduced-motion zeroes the travel like the existing chevron rule. Tree conversion moves inline style.display toggles to a class so CSS owns the motion; keyboard-nav expanded checks follow. Enforce in test_design_vocabulary.py.
