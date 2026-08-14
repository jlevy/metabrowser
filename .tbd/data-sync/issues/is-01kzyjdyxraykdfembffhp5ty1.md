---
type: is
id: is-01kzyjdyxraykdfembffhp5ty1
title: Restore Files summary count-to-bar spacing
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - folder-overview
  - pr-37
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T22:03:38.291Z
updated_at: 2026-08-13T22:11:58.435Z
closed_at: 2026-08-13T22:11:58.431Z
close_reason: Expanded the fixed metric-value column at regular and compact breakpoints, added a regression check, verified live 6px/3px label-to-bar gaps, and passed local and GitHub validation.
---
The fixed Files-value grid column is narrower than rendered labels such as ‘8,231 files’, so text overflows through the column gap and touches the distribution bar. Size the value column and responsive override so count labels retain visible separation from the bar, and validate the layout in browser and automated tests.
