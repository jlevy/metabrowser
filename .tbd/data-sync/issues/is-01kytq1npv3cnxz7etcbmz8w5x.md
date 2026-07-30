---
type: is
id: is-01kytq1npv3cnxz7etcbmz8w5x
title: Adopt KPress --kpress-font-size-base once upstream lands (collapse KPress bridge)
kind: chore
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-07-30T23:51:38.970Z
updated_at: 2026-07-30T23:51:38.970Z
---
Upstream issue https://github.com/jlevy/kpress/issues/37 proposes KPress size all typography from a single --kpress-font-size-base knob (em-internal, root-independent). Once a KPress release includes it, collapse the KPress bridge in static/styles.css (token remap + em restatements of headings/bullets/widget labels) down to setting that one variable to var(--document-body-font-size), and update docs/design-system.md (px/rem Unit Boundary). Re-verify with the two-root check (render at 16px and 13px browser roots; computed sizes must be identical).
