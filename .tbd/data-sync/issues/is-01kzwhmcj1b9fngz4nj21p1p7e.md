---
type: is
id: is-01kzwhmcj1b9fngz4nj21p1p7e
title: Contextual keyboard help and tree navigation
kind: epic
status: closed
priority: 1
version: 24
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies: []
child_order_hints:
  - is-01kzwhmd0dc6x7zp924mx1jrb6
  - is-01kzwmp3cfc54f78nzrzdnbn5v
  - is-01kzwmpf6yhydjd4btqdz0gpd4
  - is-01kzwmp9d6mgn76qgtpxvb70qz
  - is-01kzwhmdc3jqvad5w25pdww804
  - is-01kzwhmdrhp7q8g25hh0rrz7yh
  - is-01kzwhme4gyzm3akfkd83vh2sw
  - is-01kzwxryr276c162f0chz564y8
  - is-01kzwzn505z94t1zdr90g50jf7
  - is-01kzwzn5nthdfwhgdhjfbd3yn9
created_at: 2026-08-13T03:11:11.425Z
updated_at: 2026-08-13T07:23:50.742Z
closed_at: 2026-08-13T07:23:50.741Z
close_reason: All implementation, browser-validation, and review-follow-up beads are complete; the full release handoff gate passes.
---
Implement the active plan for one shortcut registry, a ? Help dialog, persistent and contextual nav hints, Quick File consolidation, and complete accessible file-tree keyboard navigation. Apply the durable design-system contracts for canonical key names, binding grammar, help copy, modal anatomy, semantic tokens, overlay lifecycle, and native main-pane behavior uniformly across every surface.

## Notes

Specification, durable design-system contracts, and file/function implementation map were completed in PR #35. All implementation, browser-validation, and review-follow-up beads are closed. Real-browser stress testing covered Help, Quick File, contextual hints, tree navigation, lazy loading, pagination, live updates, focus repair, responsive reflow, themes, and console cleanliness. The final make verify gate passes with 935 pytest cases, 30 golden scenarios, public hygiene, supply-chain policy checks, both vulnerability audits, distribution inspection, and isolated installed-wheel/API smoke tests. Implementation is complete.
