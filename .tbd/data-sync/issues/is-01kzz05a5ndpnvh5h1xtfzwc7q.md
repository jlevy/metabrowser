---
type: is
id: is-01kzz05a5ndpnvh5h1xtfzwc7q
title: Drive navigation filters from the shared registry
kind: feature
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - ui
  - navigation
dependencies:
  - type: blocks
    target: is-01kzz0681weprsdjnd151fxkhj
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:03:34.965Z
updated_at: 2026-08-14T03:14:19.275Z
closed_at: 2026-08-14T03:14:19.274Z
close_reason: Navigation type chooser now derives top-level group and per-group family sections, memberships, order, and tallies from Registry v1 while retaining exact extension choices.
---
Update InventoryIndex.navigation_tallies(), app.js type preset/family/section helpers, filter models, and menu rendering to derive ordered Code, Docs, Data, Logs, Archives, Media, and Other choices from Registry v1. Present display families plus exact canonical/raw extension children; selecting a group or family selects declared descendants; preserve exact child selection and compound suffix behavior; and keep server complete-index tallies authoritative. Tests: dynamic group order, omitted empty groups, parent/child selection and deselection, JSON Lines and media/archive cases, saved token compatibility, partial navigation loads, keyboard/menu behavior, and immutable SDK-only access. Acceptance: no hard-coded category union or extension membership remains in navigation code.
