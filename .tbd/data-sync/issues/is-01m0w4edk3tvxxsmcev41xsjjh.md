---
type: is
id: is-01m0w4edk3tvxxsmcev41xsjjh
title: S18 Include the data clock in filtered-page cache identity
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:36:26.210Z
updated_at: 2026-08-25T09:36:51.188Z
closed_at: 2026-08-25T09:36:51.187Z
close_reason: "Rebutted after contract inspection: FilteredTreeQuery.filter is an InventoryFilter value and its dataclass equality includes as_of_ns, so the memo already rejects a different data clock. Existing paged-time conformance coverage exercises the invariant; no code change is appropriate."
resolution: null
duplicate_of: null
---
The Python provider one-entry FilteredTree continuation memo matches version, path, depth, and filter but omits FilteredTreeQuery.as_of_ns. A direct provider caller can request the same recency filter at the same provider version under a different data clock and receive rows assembled at the earlier clock. Include as_of_ns in cache identity and add regression coverage proving a changed clock recomputes rather than reusing the page.
