---
type: is
id: is-01kxs093y298kftkbf4y5yense
title: Reduce excessive spacing between TOC items
kind: bug
status: closed
priority: 2
version: 3
labels:
  - ui
dependencies: []
created_at: 2026-07-17T21:38:49.409Z
updated_at: 2026-07-17T21:44:03.011Z
closed_at: 2026-07-17T21:44:03.010Z
close_reason: Fixed the Metabrowser .md-body list-margin leak into embedded KPress TOC rows, reducing measured row spacing from 39.83px to 24.63px while preserving prose list spacing; added regression coverage and passed make verify with 710 tests.
---
Rendered Markdown tables of contents have noticeably more vertical spacing between entries than earlier Metabrowser versions. Measure the current embedded KPress TOC, identify whether the regression comes from KPress defaults or Metabrowser host overrides, and restore the compact prior rhythm without changing general Markdown list spacing.
