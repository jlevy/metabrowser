---
type: is
id: is-01m0w0dd73chr6r84tnbanxv36
title: "PR #74 scope audit S4: centralize Python diagnostics assembly"
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:25:58.754Z
updated_at: 2026-08-25T08:29:13.420Z
closed_at: 2026-08-25T08:29:13.419Z
close_reason: Deduplicated into mb-tc30, whose typed diagnostics payload removes both duplicated mappings rather than only factoring them.
resolution: null
duplicate_of: null
---
_capture_image and _read_rollup_sync independently spell the same provider/contract/root/watch/catalog/work diagnostics mapping. Extract one lock-safe helper so checkpoint, ordinary, and rollup reads cannot drift and reduce the complexity of the new read paths.
