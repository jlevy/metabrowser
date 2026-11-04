---
type: is
id: is-01m6j7mhywzsbq6s41pzyrk50q
title: Keep sibling branch-copy hit targets inside clipped metadata
kind: bug
status: closed
priority: 2
version: 6
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j5ce0pgcr3zhv1w349e6bk
hold: null
hold_until: null
created_at: 2026-11-04T02:53:59.639Z
updated_at: 2026-11-04T17:14:29.629Z
started_at: 2026-11-04T02:56:01.237Z
closed_at: 2026-11-04T17:14:29.629Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent real-Chrome production CSS/helper probe at fifth frontend v2/v3 reproduces visible head-copy controls outside the clipped PR metadata ancestor at widths444–455px. At444px metadata right452px versus copy right463.64px;906visible/204hidden controls establish nonvacuity and cleanup0layers. Reuse exact probe/assertions for successor, preserve other visible controls, no row-height or navigation change. Evidence design-tokens-14433032/copy-clip-*.

## Notes

Independent unchanged Chrome width probe is green at ancestor-bound successor: 0 violations, 906 visible controls, 216 hidden controls, 0 retained layers. Bounds intersect every containing box through primary at entry only; no plugin selectors or new observers. Later v5 only adjusts copy foreground handling and retains clipping logic. Direct wide-ref-group/narrow-metadata regression plus full68 frontend checks pass. Root reserves closure/final installed acceptance.
