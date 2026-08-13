---
type: is
id: is-01kzyczrr4v4skw0nvnn7rnqmy
title: Unify collapsible section headers across Overview and Markdown
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - ui
  - design-system
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T20:28:30.339Z
updated_at: 2026-08-13T20:39:53.578Z
closed_at: 2026-08-13T20:39:53.577Z
close_reason: Implemented and documented one accessible trailing-chevron section disclosure across Overview and Markdown. Files and README start expanded without remounting on collapse; Frontmatter and Diagnostics start collapsed. Added lifecycle, style, default-state, reduced-motion, print, and real-render coverage; live browser validation and make verify pass.
---
Add one accessible section-disclosure design pattern with a gray text-scaled trailing chevron. Make Overview Files and README panels collapsible and initially expanded; keep Markdown Frontmatter and Diagnostics collapsible and initially collapsed. Preserve content lifecycle and document rendering behavior.
