---
type: is
id: is-01m01786ym79wmymtcnzbaz8rd
title: Unify folder totals and type rollups into one Files section
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T22:45:58.867Z
updated_at: 2026-08-14T23:04:40.630Z
closed_at: 2026-08-14T23:04:40.629Z
close_reason: Implemented one collapsible Files section with a single Files/Bytes metric column, fixed Total and Ignored context, scope-only Show ignored behavior, shared Treemap controls, current design documentation, TDD coverage, live browser validation, and a green make verify gate.
---
Replace the parallel Files and Size columns with one selected metric column shared by totals and type rollups. The Overview exposes one collapsible Files section, open by default, with a Files/Bytes chooser. Total and Ignored rows always remain visible and switch their displayed value and normalized bar with the selected metric. Show ignored appears after totals and affects only the type breakdown below; totals continue to show both Total and Ignored so the scope is explicit. Reuse the same single-metric totals renderer and chooser in Treemap so the two folder views retain one control grammar. Update behavior, DOM, style, accessibility, and design documentation tests. Acceptance: no visible parallel metric columns remain; Files is the default; switching to Bytes changes all displayed values and sort/bar scaling atomically; toggling Show ignored changes breakdowns and Treemap content without hiding or changing the Total and Ignored population rows; empty and loading folders remain stable without partial rows.
