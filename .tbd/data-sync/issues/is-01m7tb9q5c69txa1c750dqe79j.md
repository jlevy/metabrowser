---
type: is
id: is-01m7tb9q5c69txa1c750dqe79j
title: "Host mode H2: the server record contract and the ready-line flag"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7tb9tfnm9f644mc5sm6ab5e
  - type: blocks
    target: is-01m7tb9zw4d1mkfhh9kbz4r7mk
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-19T16:47:36.107Z
updated_at: 2026-11-19T16:47:45.028Z
---
Host mode plan step H2 (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan; Decisions HM-1 A, HM-2 A, and HM-6 A, taken 2026-11-19). Split from mb-qzny.

Delivers: the server record as one contract in a metabrowser.host family beside metabrowser.ui, served by /api/contract, holding the fields the plan's Discovery section lists and never a credential, with a protocol number that is a hard gate as PLUGIN_SDK_VERSION is; and a serve flag that prints the record as one JSON line at H1's ready moment. The macOS app adopts the line through its ServerLaunch seam in place of the serving line docs/project/architecture/arch-app-contract.md declares, in the same commit. A golden of the line, its parity row, and the reference-host test.

Slot: after H1; in Ordering 2, after T0.7 and V2, whose family registry it follows.
