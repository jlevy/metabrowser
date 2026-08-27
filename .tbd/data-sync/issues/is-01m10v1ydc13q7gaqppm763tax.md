---
type: is
id: is-01m10v1ydc13q7gaqppm763tax
title: "Spike: validate the exact-wheel fdu provider against the MetaBrowser contract"
kind: task
status: open
priority: 1
version: 6
labels: []
dependencies: []
child_order_hints:
  - is-01m1108krqtakrjwazn3eycbp1
created_at: 2026-08-27T05:28:32.426Z
updated_at: 2026-08-27T07:55:12.877Z
---
On branch codex/fdu-opened-root-e2e-spike at PR #74 head 3183888, install an fdu wheel built from exact PR #48 revision 0583a1a, implement the minimum disposable adapter to the unchanged InventoryHandle contract, instrument materialization/sort/aggregate/binding costs, and run one full application lifecycle. Preserve the Python provider and standalone fdu CLI. Retain the reproducible harness and evidence; delete or replace naive adapter code after the contract decision.

## Notes

Phase 3A exact-wheel evidence remains reproducible at fdu 0583a1a. The disposable adapter passes lifecycle cleanup, 9/12 original provider cases, 12/13 original route/SSE cases, and records 8,830 rows / 412,836 path bytes / about 852 ms / about 13 MB traced allocation. MetaBrowser commits 9cf1d87, 0a6ddbb, and 6ae1468 completed resource-stop, scope/classification, facade removal, and lifecycle vocabulary alignment. The current contract checkpoint adds opaque one-shot version-pinned paging, non-consuming work-limit retries, exact-or-lower-bound counts, deterministic semantic work separated from boundary metrics, canonical portable ordering, portable-path loss records, one active provider change iterator, and bounded host assembly. The complete gate passes 1,633 pytest cases and 48 CLI golden scenarios. Keep open until the disposable adapter is replaced or deleted after the production fdu provider lands.
