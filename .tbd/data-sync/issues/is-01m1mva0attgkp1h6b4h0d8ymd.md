---
type: is
id: is-01m1mva0attgkp1h6b4h0d8ymd
title: "PR #101 R3.5: metab --walk bypasses the coordinator in both modes"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:45.177Z
updated_at: 2026-09-03T23:57:45.177Z
---
Both walk.py:133 text mode and walk.py:562 --stream bypass the coordinator, not just --stream as #99 recorded; walk.py:401 constructs InventoryRuntime(config=config) ignoring METABROWSER_INVENTORY_PROVIDER entirely. walk_collect also omits hidden_allowlist, agreeing with the provider only by coincidence of defaults. With a second provider these surfaces would describe an engine that is not running.
