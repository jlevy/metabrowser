---
type: is
id: is-01m01dda2hvpg3z26zat55edg8
title: Split Overview totals and file breakdown sections
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T00:33:37.352Z
updated_at: 2026-08-15T00:52:32.478Z
closed_at: 2026-08-15T00:52:32.477Z
close_reason: Implemented and verified end to end; Files is open, File Breakdown is closed, controls are shared, and the documented default scope is checked.
---
Restore two coordinated Overview sections. Files is open by default and owns the one shared Files/Bytes chooser plus disjoint Files and Ignored totals. File Breakdown is closed by default and contains the complete type distribution. The shared metric changes totals, breakdown, and Treemap together without duplicate Overview controls. Show ignored reuses the navigation-panel checkbox treatment and defaults checked for rollup projections. Cover default state, coordinated updates, disposal, and accessible section semantics with behavior tests; update the design-system contract.

## Notes

Implemented with TDD. Added separate Files totals and File Breakdown panels, one shared metric state across Overview and Treemap, default-on nav-style Show ignored, disposal-safe subscriptions, and synchronized architecture/design/spec documentation. Focused 84-test suite and full make verify pass.
