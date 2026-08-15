---
type: is
id: is-01m01eww2jg7w5akz196jv6sff
title: Segment Files and Ignored totals by file type
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T00:59:35.889Z
updated_at: 2026-08-15T01:21:47.660Z
closed_at: 2026-08-15T01:21:47.659Z
close_reason: null
---
Replace the neutral population bars in the default-open Files Overview panel with full-width, internally segmented semantic file-type composition bars. Files remains the disjoint non-ignored population and Ignored remains the disjoint ignored population; each row shows only its selected-metric absolute tally because its own bar is the 100% denominator. Reuse File Breakdown category colors and rollup data without another crawl, preserve immediate totals while detail is pending, dim the entire Ignored row consistently with ignored navigation entries, cover counts and bytes plus empty/zero populations and lifecycle disposal with TDD, and update architecture/design/spec documentation.
