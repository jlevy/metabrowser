---
type: is
id: is-01m26hjjvhpcf49p2x1c3390kk
title: Complete functional UI parity inventory and golden migration
kind: epic
status: open
priority: 2
version: 18
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels:
  - linear
  - Improvement
dependencies: []
child_order_hints:
  - is-01m26hk1tsbhqda5640dzg84kc
  - is-01m26hk24se2htkqr2vxes86ya
  - is-01m26hk2et8695fjsez459t8r3
  - is-01m26hk2rrsnkw60php7gkadpy
  - is-01m26hk32t3ke05ttrpvn7xwy8
  - is-01m27nw4m7ygtadwf6mm3d6qtz
  - is-01m2eb9q0b31d97jb0g6kxcc1d
  - is-01m188e19j8gqnzdvhcrrn93qc
  - is-01m7ewneb9hbrwwqrxdr65q914
  - is-01m7re714zs51hx8dw5126eex9
  - is-01m7pr9x6jds5pb33d72apcyqp
created_at: 2026-09-10T20:54:00.303Z
updated_at: 2026-11-20T19:16:30.440Z
extensions:
  linear:
    id: b5547486-4b75-4916-b8ea-90d52974dfb2
    linked_at: 2026-11-20T19:16:30.429Z
---
Migrate the existing UI from broad DOM/source checks to the parity principle introduced by the release-hardening work: every observable data decision is reachable through metab and golden-pinned; every browser-owned interaction state machine executes exact production code in a deterministic CLI golden; only paint/platform behavior has a narrow documented exemption with focused browser evidence. The initial release mechanism is an enforced seed, not a claim that all legacy UI has already migrated. Group rows by user-observable contracts rather than helper files, and keep runtime paths, persisted state, errors, cancellation, disposal, and stale-response behavior explicit.

## Notes

2026-11-14 audit: Phase 4 remains open; the spec now notes which surfaces feature work has already registered.

2026-11-20 audit: Parity and golden migration; open children are golden-pin tasks and checker work. mb-tl4e and mb-r716 were added.
