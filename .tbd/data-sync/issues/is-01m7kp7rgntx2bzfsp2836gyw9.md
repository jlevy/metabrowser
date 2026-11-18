---
type: is
id: is-01m7kp7rgntx2bzfsp2836gyw9
title: Thin fdu adapter with factory entry, flag, and extra (R10, R11, R14, R31)
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7rwg98164mggx64spn2j
  - type: blocks
    target: is-01m7kp7s7mp21yntm16hx21cv6
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:05.269Z
updated_at: 2026-11-18T01:29:47.609Z
---
In one change: providers/fdu_inventory.py answering natively or failing typed per unsupported kind (D12), the fdu factory entry, metab --inventory-provider, the metabrowser[fdu] extra with exact pin, environment marker, and supply-chain review, and route handling for unpinned VersionUnavailableError. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, The Production Adapter.

## Notes

Deferred to the next release (user, 2026-11-18): the fdu-independent groundwork stack (mb-r75q) merges first on the Python provider; this adapter, its factory entry, the experimental --inventory-provider flag and the metabrowser[fdu] extra are the switchover and land in the next release, still blocked on fdu's open-time group (mb-xd56).
