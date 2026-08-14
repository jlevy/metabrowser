---
type: is
id: is-01kzyp7mj195jbenqsm6y8e2af
title: Add category and family tiers to the navigation type chooser
kind: feature
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/done/plan-2026-08-13-semantic-file-type-families.md
labels:
  - file-types
  - navigation
  - accessibility
dependencies:
  - type: blocks
    target: is-01kzyp89g0kfj93q870sgbaqzk
parent_id: is-01kzyp6zfgt2xkj2wepzx6n5cq
created_at: 2026-08-13T23:10:05.376Z
updated_at: 2026-08-14T00:21:23.862Z
closed_at: 2026-08-14T00:18:08.467Z
close_reason: Implemented category, present-family, and canonical/raw tiers with authoritative counts, compound-suffix matching, additive parent selection, exact summaries, and preserved menu accessibility.
---
Generalize filter_controls.menuGroupHtml to ordered aggregate sections, then update app.js and filter_state.js to show Docs, Code, and Data; present semantic families; and canonical/raw extensions. Preserve additive parent selection, current-population tallies, ignored-file reranking, exact group summaries, menu keyboard behavior, and the raw extension cap. Canonicalize every tree, lazy subtree, Recent, and live-overlay row through the shared taxonomy so a .js selection includes compound .js tails.
