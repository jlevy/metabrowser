---
type: is
id: is-01m0w0cf5a14es50yf4sq3c26d
title: "PR #74 scope audit S2: trim legacy Python store compatibility surface"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:25:27.977Z
updated_at: 2026-08-25T09:57:01.056Z
closed_at: 2026-08-25T09:57:01.056Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
The private Python provider retained unused InventoryIndex-era max_files/max_depth constructor arguments, catalog accessors, wire-scope spellings, and walker/default re-exports. Remove production-dead members and re-exports, retain the zero-argument default InventoryConfig test seam to avoid 33 mechanical call-site edits, update tests to import the true walker owner, and rewrite the stale module description around the five-method handle.
