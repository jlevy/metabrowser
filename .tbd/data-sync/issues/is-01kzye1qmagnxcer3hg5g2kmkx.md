---
type: is
id: is-01kzye1qmagnxcer3hg5g2kmkx
title: Keep nested Treemap cells visible during container hover
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - ui
  - treemap
  - regression
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-13T20:47:03.305Z
updated_at: 2026-08-13T20:55:38.709Z
closed_at: 2026-08-13T20:55:38.709Z
close_reason: Fixed Treemap metric selection feedback and nested-container hover layering with focused regression coverage, live-browser validation, and updated design and architecture contracts.
---
Hovering a Treemap directory container must only change that container's own fill. Descendant folder/file cells must retain their color, stacking, and visibility; no hover rule may cover, hide, or reorder nested cells. Add regression coverage for the nested hover contract.
