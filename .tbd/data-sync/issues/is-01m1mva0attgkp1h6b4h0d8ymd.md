---
type: is
id: is-01m1mva0attgkp1h6b4h0d8ymd
title: "PR #101 R3.5: metab --walk bypasses the coordinator in both modes"
kind: bug
status: open
priority: 1
version: 3
labels: []
dependencies:
  - type: blocks
    target: is-01m0r8xt95921dabcddjjm7csf
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:45.177Z
updated_at: 2026-09-08T00:02:50.407Z
---
Both walk.py:133 text mode and walk.py:562 --stream bypass the coordinator, not just --stream as #99 recorded; walk.py:401 constructs InventoryRuntime(config=config) ignoring METABROWSER_INVENTORY_PROVIDER entirely. walk_collect also omits hidden_allowlist, agreeing with the provider only by coincidence of defaults. With a second provider these surfaces would describe an engine that is not running.

## Notes

JSON/YAML walk now selects the configured provider through inventory_provider_from_environment; a regression rejects an unknown configured provider rather than silently using Python. Text and --stream still expose the explicit Python walker diagnostic. Keep this bead open to settle their provider semantics before native adoption; do not describe the whole CLI as provider-selectable yet.
