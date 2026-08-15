---
type: is
id: is-01m01vm44p61h5rg11vb2frysy
title: Align Overview panels to the README card
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T04:42:00.725Z
updated_at: 2026-08-15T04:50:02.641Z
closed_at: 2026-08-15T04:50:02.640Z
close_reason: Aligned Files, File Breakdown, and README section chrome to the visible KPress card at regular widths, preserved the narrow prose and wide TOC contracts, documented the shared geometry, added regression coverage, verified exact live edges, and passed make verify.
---
Correct the responsive Folder Overview alignment contract so Files, File Breakdown, and README section headings and flat panel bodies align to the rendered README card's outer edges at regular and wide widths, without narrowing the document card or changing KPress's borderless narrow behavior. Derive the shared measure from the actual document surface geometry, cover regular/wide/narrow CSS contracts with TDD, document the reusable alignment rule, and verify the live layout.
