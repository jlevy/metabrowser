---
type: is
id: is-01kzyp7mj195jbenqsm6y8e2af
title: Add category and family tiers to the navigation type chooser
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-semantic-file-type-families.md
labels:
  - file-types
  - navigation
  - accessibility
dependencies:
  - type: blocks
    target: is-01kzyp89g0kfj93q870sgbaqzk
parent_id: is-01kzyp6zfgt2xkj2wepzx6n5cq
created_at: 2026-08-13T23:10:05.376Z
updated_at: 2026-08-13T23:10:26.815Z
---
Generalize filter_controls.menuGroupHtml to ordered aggregate sections, then update app.js and filter_state.js to show Docs, Code, and Data; present semantic families; and canonical/raw extensions. Preserve additive parent selection, current-population tallies, ignored-file reranking, exact group summaries, menu keyboard behavior, and the raw extension cap. Canonicalize every tree, lazy subtree, Recent, and live-overlay row through the shared taxonomy so a .js selection includes compound .js tails.
