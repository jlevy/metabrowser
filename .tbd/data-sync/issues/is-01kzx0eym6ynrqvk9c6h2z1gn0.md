---
type: is
id: is-01kzx0eym6ynrqvk9c6h2z1gn0
title: Redesign File types as grouped inline-bar table
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels: []
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T07:30:21.955Z
updated_at: 2026-08-13T07:54:03.738Z
closed_at: 2026-08-13T07:54:03.734Z
close_reason: Replaced aggregate distributions with the grouped Type/Files/Size table; added total-normalized row fills, shared Code/Data/Other classification, responsive alignment, design/spec updates, DOM/model coverage, live browser review, and a passing full make verify gate.
---
Replace the aggregate Files/Size bars and legend rows with a single fixed-layout comparison table. Group rows under Code, Data, and Other subheadings using existing file classification where possible. Each Files and Size cell shows a left-aligned per-column normalized bar, a right-aligned absolute tally, and a right-aligned percentage; preserve stable per-type colors but remove decorative circle marks. Update the completed spec, design system, tests, live preview, and PR #37.
