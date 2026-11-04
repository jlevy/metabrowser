---
type: is
id: is-01m6j7mhywzsbq6s41pzyrk50q
title: Keep sibling branch-copy hit targets inside clipped metadata
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j5ce0pgcr3zhv1w349e6bk
hold: null
hold_until: null
created_at: 2026-11-04T02:53:59.639Z
updated_at: 2026-11-04T02:56:03.455Z
started_at: 2026-11-04T02:56:01.237Z
---
Independent real-Chrome production CSS/helper probe at fifth frontend v2/v3 reproduces visible head-copy controls outside the clipped PR metadata ancestor at widths444–455px. At444px metadata right452px versus copy right463.64px;906visible/204hidden controls establish nonvacuity and cleanup0layers. Reuse exact probe/assertions for successor, preserve other visible controls, no row-height or navigation change. Evidence design-tokens-14433032/copy-clip-*.

## Notes

Confirmed real narrow-row ancestor clipping repro from independent reviewer. Fixed SDK mountRefCopies at hash fd3a173ff9e90e863197a3288e6ed1450e934c7e916336857f5843238a36369b: intersect all containing boxes through primary only on pointer/focus entry; no plugin selectors/global observers. Added production helper regression for a wide refs group clipped by a narrower metadata ancestor. Original browser width probe awaiting independent recheck; do not close until acceptance.
