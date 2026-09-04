---
type: is
id: is-01m1mv96p8sz76mv2ssdpf69ek
title: "PR #101 R2a: a literal % in a filename breaks every inbound lookup"
kind: bug
status: closed
priority: 0
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:18.919Z
updated_at: 2026-09-04T02:07:11.802Z
closed_at: 2026-09-04T02:07:11.801Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
BLOCKER, reproduced. Outbound canonical_inventory_path escapes % to %25 (contract.py:263-281); inbound parse_inventory_path never un-escapes and _entries is keyed raw (python_inventory.py:1137). Repro on macOS: d%1 publishes as d%251 and expands to 0 children; report%20final.txt publishes as report%2520final.txt and EntryQuery returns ABSENT. Also a display regression: the escaped name is what the browser shows. Works on main.
