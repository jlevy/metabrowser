---
type: is
id: is-01m00phs4p1dvrzhgay8fqvwwr
title: Separate overview File Totals and File Types sections
kind: feature
status: open
priority: 2
version: 1
labels:
  - browser
  - folder-overview
dependencies: []
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T17:54:06.613Z
updated_at: 2026-08-14T17:54:06.613Z
---
Restructure the folder overview so rollup totals and the type distribution have separate, clearly scoped sections.

Required behavior:
- Replace the combined Files presentation with File Totals followed immediately by File Types, before README or later optional overview panels.
- File Totals is always expanded and has no disclosure control. It contains the Total and Ignored rows, including both file counts and byte sizes with their normalized bars and percentages.
- Keep the Ignored row in File Totals independently of the File Types Show ignored filter so users can always see the excluded subset.
- File Types is a standard collapsible section using the shared trailing-chevron section-header design and is open by default.
- Mount the shared Bytes versus Files and Show ignored controls directly below the File Types heading. Those controls affect only the type breakdown below them, not the File Totals figures.
- Keep headings, content edges, spacing, responsive behavior, and disclosure semantics aligned with the README and existing overview design system.
- Split rendering responsibilities cleanly so totals and type rows can update independently while consuming the same complete rollup snapshot.
- Add DOM behavior and CSS contract tests for order, default expansion, fixed totals visibility, control placement and scope, responsive alignment, empty states, and disposal.
