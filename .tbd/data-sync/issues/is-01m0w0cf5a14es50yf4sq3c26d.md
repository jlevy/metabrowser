---
type: is
id: is-01m0w0cf5a14es50yf4sq3c26d
title: "PR #74 scope audit S2: trim legacy Python store compatibility surface"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:25:27.977Z
updated_at: 2026-08-25T09:33:21.160Z
---
The private Python provider retained unused InventoryIndex-era max_files/max_depth constructor arguments, catalog accessors, wire-scope spellings, and walker/default re-exports. Remove production-dead members and re-exports, retain the zero-argument default InventoryConfig test seam to avoid 33 mechanical call-site edits, update tests to import the true walker owner, and rewrite the stale module description around the five-method handle.
