---
type: is
id: is-01kzwkxst27f1wrrq2ktft2jmy
title: Implement the dual-metric File types panel
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - frontend
dependencies:
  - type: blocks
    target: is-01kzwky52tcet4twn7e4eknkje
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:51:17.056Z
updated_at: 2026-08-13T06:16:35.833Z
closed_at: 2026-08-13T06:16:35.833Z
close_reason: Implemented and validated on codex/folder-overview-implementation; focused coverage and make verify pass.
---
Implement file_type_summary_model.js, distribution_view.js, file_type_summary.js, Overview and summary CSS, shared distribution tokens/utilities in static/styles.css, and folder manifest style wiring. Register the required folder.file-types surface panel; request a depth/top-zero dual rollup; render paired Files/Size bars and an exact semantic table; switch all/unignored locally; persist disclosure; gate hidden refresh; isolate Retry; preserve focus; handle pending, partial, truncated, empty, ignored-only, zero-byte, and failure states. Add pure and DOM tests for arithmetic, formatting, a11y, keyed updates, lifecycle, filters, responsive structure, and 0 files · 0 B with no bars/table.
