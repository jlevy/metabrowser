---
type: is
id: is-01m10v1ydc13q7gaqppm763tax
title: "Spike: validate the exact-wheel fdu provider against the MetaBrowser contract"
kind: task
status: open
priority: 1
version: 4
labels: []
dependencies: []
created_at: 2026-08-27T05:28:32.426Z
updated_at: 2026-08-27T06:52:57.361Z
---
On branch codex/fdu-opened-root-e2e-spike at PR #74 head 3183888, install an fdu wheel built from exact PR #48 revision 0583a1a, implement the minimum disposable adapter to the unchanged InventoryHandle contract, instrument materialization/sort/aggregate/binding costs, and run one full application lifecycle. Preserve the Python provider and standalone fdu CLI. Retain the reproducible harness and evidence; delete or replace naive adapter code after the contract decision.

## Notes

Phase 3A exact-wheel evidence remains reproducible at fdu 0583a1a. The disposable adapter passes lifecycle cleanup, 9/12 original provider cases, 12/13 original route/SSE cases, and records 8,830 rows / 412,836 path bytes / about 852 ms / about 13 MB traced allocation. MetaBrowser commits 9cf1d87 and 0a6ddbb complete resource-stop parity and the shared scope/classification checkpoint: discovery budget is execution policy, depth belongs to queries, config names the supported filesystem scope, and supplied registry content drives identity, filters, navigation tallies, and rollups. The complete gate passes 1,623 pytest cases and 48 CLI golden scenarios. Keep open until the disposable adapter is replaced or deleted after the revised contract and production fdu provider land.
