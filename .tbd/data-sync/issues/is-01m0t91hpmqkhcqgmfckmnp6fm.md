---
type: is
id: is-01m0t91hpmqkhcqgmfckmnp6fm
title: Avoid repeated whole-index scans when assembling the catalog
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies: []
parent_id: is-01m0t8bsb54j16rhfdmwj5q0vh
created_at: 2026-08-24T16:18:18.452Z
updated_at: 2026-08-24T16:50:29.382Z
closed_at: 2026-08-24T16:50:29.381Z
close_reason: Bound Python catalog assembly to one full-index provider page, copied one immutable image under lock, and retained generic version-pinned continuation semantics; measured and fully verified.
resolution: null
duplicate_of: null
---
_read_catalog requests 50,000-row pages, while the Python provider rescans and resorts every catalog match for each continuation. At the 500,000-entry scope this can repeat the full O(N log N) work ten times. Use the provider's configured retained-entry bound for the complete Python-phase catalog read, retain version-pinned continuation support for providers that can page efficiently, and add work-counter coverage proving catalog assembly does not multiply whole-index visits by page count.

## Notes

Catalog assembly now requests InventoryConfig.max_entries, a hard upper bound on retained entries and therefore on catalog files. The Python provider copies one immutable image under its writer lock and filters/sorts outside it; the route preserves generic pinned continuation but the Python scope completes in one provider page. Focused tests pass.
