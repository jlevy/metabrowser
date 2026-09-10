---
type: is
id: is-01m24prxgbn1g54s2q6jwj3b2w
title: Make development version identity advance past maintenance releases
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies:
  - type: blocks
    target: is-01m24nhxxpkrb7cvgyvtxb5d0r
parent_id: is-01m24nhxxpkrb7cvgyvtxb5d0r
created_at: 2026-09-10T03:46:21.823Z
updated_at: 2026-09-10T05:00:03.515Z
closed_at: 2026-09-10T05:00:03.513Z
close_reason: Merged the published v0.9.1 release commit into the release-hardening ancestry without changing the current product tree. Fresh editable metadata and a clean wheel now report 0.9.2.dev124+f097c667, which orders after v0.9.1; the merge also restores the v0.9.1 release's committed performance evidence.
resolution: null
duplicate_of: null
---
Current main derives 0.9.1.devN from the v0.9.0 ancestor even though v0.9.1 is the latest published maintenance tag and is not in main ancestry, so package ordering places the development build before the installed release. Define a truthful, automatic development identity that remains upgradeable after maintenance-line releases without speculative compatibility logic.
