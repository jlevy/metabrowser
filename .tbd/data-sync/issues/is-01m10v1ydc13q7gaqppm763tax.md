---
type: is
id: is-01m10v1ydc13q7gaqppm763tax
title: "Spike: validate the exact-wheel fdu provider against the MetaBrowser contract"
kind: task
status: open
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-27T05:28:32.426Z
updated_at: 2026-08-27T06:24:49.616Z
---
On branch codex/fdu-opened-root-e2e-spike at PR #74 head 3183888, install an fdu wheel built from exact PR #48 revision 0583a1a, implement the minimum disposable adapter to the unchanged InventoryHandle contract, instrument materialization/sort/aggregate/binding costs, and run one full application lifecycle. Preserve the Python provider and standalone fdu CLI. Retain the reproducible harness and evidence; delete or replace naive adapter code after the contract decision.

## Notes

Phase 3A checkpoint complete at fdu revision 0583a1a and MetaBrowser contract revision 3183888. The exact-wheel runner passes lifecycle/cleanup and 9/12 provider cases plus 12/13 selected route/SSE cases. The remaining differences identified by the spike were resource-stop phase, provider-batch journal capacity, provider-owned discovery barrier, and host coalescing. The materializing oracle measured 8,830 rows / 412,836 path bytes / about 852 ms / about 13 MB traced Python allocation on the provisioned checkout. Resource-stop parity is now implemented on the spike branch: budget refusal is terminal and readable, joins observation with a resource_budget diagnostic, permits retained-leaf verification, rejects scope-expanding refresh, and makes priority inert. The focused provider suite passes 84 tests and the complete MetaBrowser gate passes 1,621 pytest cases plus 48 CLI golden scenarios. Keep this bead open until the disposable adapter is replaced or deleted after the Phase 3B contract decision.
