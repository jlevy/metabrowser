---
type: is
id: is-01kzy2391qr2r6mbjc2hhwytyc
title: "Treemap controls: metric toggle plus default-on ignored checkbox"
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
created_at: 2026-08-13T17:18:10.998Z
updated_at: 2026-08-13T18:12:40.584Z
closed_at: 2026-08-13T18:12:40.583Z
close_reason: Implemented the Bytes/Files control and default-on Show ignored checkbox with legacy-state sanitization and interaction coverage.
---
Simplify the Folder Treemap toolbar and persisted state. Keep only the Bytes/Files metric segmented control. Replace the three-state ignored selector with a labelled checkbox whose checked state includes gitignored entries and whose unchecked state excludes them; default to checked. Migrate or sanitize older saved grouping/color/ignored preferences without retaining obsolete behavior. Acceptance: no grouping or color selectors remain, no dimmed-only mode remains, checkbox polarity is accessible and obvious, status/layout agree with scope, and interaction tests cover persistence-free relayout without refetch.
