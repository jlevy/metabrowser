---
type: is
id: is-01kzye1q14x441xkz8gtpva03e
title: Fix Treemap Bytes and Files metric switching
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
created_at: 2026-08-13T20:47:02.692Z
updated_at: 2026-08-13T20:55:38.700Z
closed_at: 2026-08-13T20:55:38.699Z
close_reason: Fixed Treemap metric selection feedback and nested-container hover layering with focused regression coverage, live-browser validation, and updated design and architecture contracts.
---
The Treemap Bytes/Files segmented chooser does not visibly recompute geometry and values when the selected metric changes. Reproduce against the live repository view, repair the state/render path, and add regression coverage proving the same rollup renders differently for byte and file weights.
