---
type: is
id: is-01kzwhmcj1b9fngz4nj21p1p7e
title: Contextual keyboard help and tree navigation
kind: epic
status: closed
priority: 1
version: 18
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
created_at: 2026-08-13T03:11:11.425Z
updated_at: 2026-08-13T07:01:31.057Z
closed_at: 2026-08-13T07:01:31.056Z
close_reason: All implementation and validation beads are closed. Shared shortcut dispatch, Help and hints, modal lifecycle, Quick File migration, accessible tree navigation, live/paged focus repair, documentation, packaging, and end-to-end validation are complete.
---
Implement the active plan for one shortcut registry, a ? Help dialog, persistent and contextual nav hints, Quick File consolidation, and complete accessible file-tree keyboard navigation. Apply the durable design-system contracts for canonical key names, binding grammar, help copy, modal anatomy, semantic tokens, overlay lifecycle, and native main-pane behavior uniformly across every surface.

## Notes

Specification and durable design-system contracts are published in draft PR #35. Commits aee1139 and 9c915a3 established the behavior, exact copy, key vocabulary, physical-key ARIA policy, overlay lifecycle, and conformance requirements. The 2026-08-12 implementation-map pass traced the current source and tests and added exact files, named functions, render-path hooks, test seams, distribution updates, and dependency order to the active spec. Precommit review tightened the map against the WAI-ARIA tree pattern: adjacent folder groups use aria-owns, dynamic nodes declare level/position/set metadata, known-empty folders remain end nodes, modal controls use surface-owned bindings with keyed trigger reconciliation and explicit detached-focus fallback, and Close, scrim, and Escape invoke one component-lifetime descriptor under an open-time scope activation. The epic has seven dependency-ordered implementation beads: registry, modal, Help/chrome, Quick File migration, pure tree navigator, app render integration, and end-to-end validation. The full make verify gate passed with 915 pytest cases, 30 golden scenarios, public hygiene, both audits, build, distribution inspection, and isolated wheel/API smoke tests. Implementation remains open.
