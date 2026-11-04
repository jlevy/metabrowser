---
type: is
id: is-01m6j7mhywzsbq6s41pzyrk50q
title: Keep sibling branch-copy hit targets inside clipped metadata
kind: bug
status: in_progress
priority: 2
version: 5
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j5ce0pgcr3zhv1w349e6bk
hold: null
hold_until: null
created_at: 2026-11-04T02:53:59.639Z
updated_at: 2026-11-04T03:03:55.737Z
started_at: 2026-11-04T02:56:01.237Z
---
Independent real-Chrome production CSS/helper probe at fifth frontend v2/v3 reproduces visible head-copy controls outside the clipped PR metadata ancestor at widths444–455px. At444px metadata right452px versus copy right463.64px;906visible/204hidden controls establish nonvacuity and cleanup0layers. Reuse exact probe/assertions for successor, preserve other visible controls, no row-height or navigation change. Evidence design-tokens-14433032/copy-clip-*.

## Notes

Independent unchanged Chrome width probe is green at ancestor-bound successor: 0 violations, 906 visible controls, 216 hidden controls, 0 retained layers. Bounds intersect every containing box through primary at entry only; no plugin selectors or new observers. Later v5 only adjusts copy foreground handling and retains clipping logic. Direct wide-ref-group/narrow-metadata regression plus full68 frontend checks pass. Root reserves closure/final installed acceptance.
