---
type: is
id: is-01kzx0eym6ynrqvk9c6h2z1gn0
title: Redesign File types as grouped inline-bar table
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels: []
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T07:30:21.955Z
updated_at: 2026-08-13T08:23:38.884Z
closed_at: 2026-08-13T08:23:38.884Z
close_reason: Restored README's standard responsive Markdown card while keeping File types flat and aligning chrome to card edges at regular/wide widths and prose edges when narrow; make verify, live browser review, and CI pass.
---
Replace the aggregate Files/Size bars and legend rows with a single fixed-layout comparison table. Group rows under Code, Data, and Other subheadings using existing file classification where possible. Each Files and Size cell shows a left-aligned per-column normalized bar, a right-aligned absolute tally, and a right-aligned percentage; preserve stable per-type colors but remove decorative circle marks. Update the completed spec, design system, tests, live preview, and PR #37.
