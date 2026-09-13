---
type: is
id: is-01m26hjjvhpcf49p2x1c3390kk
title: Complete functional UI parity inventory and golden migration
kind: epic
status: open
priority: 2
version: 8
labels: []
dependencies: []
child_order_hints:
  - is-01m26hk1tsbhqda5640dzg84kc
  - is-01m26hk24se2htkqr2vxes86ya
  - is-01m26hk2et8695fjsez459t8r3
  - is-01m26hk2rrsnkw60php7gkadpy
  - is-01m26hk32t3ke05ttrpvn7xwy8
  - is-01m27nw4m7ygtadwf6mm3d6qtz
  - is-01m2eb9q0b31d97jb0g6kxcc1d
created_at: 2026-09-10T20:54:00.303Z
updated_at: 2026-09-13T21:38:13.642Z
---
Migrate the existing UI from broad DOM/source checks to the parity principle introduced by the release-hardening work: every observable data decision is reachable through metab and golden-pinned; every browser-owned interaction state machine executes exact production code in a deterministic CLI golden; only paint/platform behavior has a narrow documented exemption with focused browser evidence. The initial release mechanism is an enforced seed, not a claim that all legacy UI has already migrated. Group rows by user-observable contracts rather than helper files, and keep runtime paths, persisted state, errors, cancellation, disposal, and stale-response behavior explicit.
