---
type: is
id: is-01kzx0eym6ynrqvk9c6h2z1gn0
title: Redesign File types as grouped inline-bar table
kind: task
status: closed
priority: 1
version: 12
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels: []
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T07:30:21.955Z
updated_at: 2026-08-13T16:31:22.327Z
closed_at: 2026-08-13T16:31:22.326Z
close_reason: Removed the redundant ignored-scope notice; added an exact neutral Ignored footer row above Total; fixed Overview mount lifetime so Show ignored updates stay live; updated architecture, design system, spec, tests, and responsive browser validation.
---
Replace the aggregate Files/Size bars and legend rows with a single fixed-layout comparison table. Group rows under Code, Data, and Other subheadings using existing file classification where possible. Each Files and Size cell shows a left-aligned per-column normalized bar, a right-aligned absolute tally, and a right-aligned percentage; preserve stable per-type colors but remove decorative circle marks. Update the completed spec, design system, tests, live preview, and PR #37.
