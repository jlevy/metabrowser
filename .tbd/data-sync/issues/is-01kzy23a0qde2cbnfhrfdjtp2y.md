---
type: is
id: is-01kzy23a0qde2cbnfhrfdjtp2y
title: "Treemap typography: fluid cell labels with shared value formatting"
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - ui
  - treemap
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-13T17:18:11.990Z
updated_at: 2026-08-13T18:12:41.046Z
closed_at: 2026-08-13T18:12:41.045Z
close_reason: Implemented bounded geometry-scaled labels and shared file-count/byte formatting with nested-header layout coverage.
---
Scale Treemap folder/file names and value labels continuously from cell geometry, with conservative lower and upper bounds so small cells stay readable and large cells use available space. Use the common Metabrowser formatters for byte sizes and file counts everywhere visible and accessible. Acceptance: typography is monotonic and bounded, large rectangles render materially larger labels and values, nested headers do not overlap children, CSS uses design tokens/custom properties rather than local theme colors, and browser tests cover representative small/large cells.
