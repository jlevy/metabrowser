---
type: is
id: is-01m00tx6gyn0xgntj5bh9400qw
title: Add parent-folder navigation above Treemap
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - treemap
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T19:10:15.069Z
updated_at: 2026-08-14T19:28:10.872Z
closed_at: 2026-08-14T19:28:10.870Z
close_reason: Implemented and validated Treemap parent navigation, removed the redundant visible totals column header, and unified the File Totals title across Overview and Treemap.
---
Add a visible, accessible parent-folder control immediately above the Treemap visualization. It identifies the enclosing folder, preserves the Treemap view when activated, reuses the same parent-path route as keyboard navigation, and is omitted at the browsed root. Cover root, nested, click, and disposal behavior with DOM tests and document the design-system contract.
