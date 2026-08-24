---
type: is
id: is-01m0t65jhkhac6432f3jbmxzwe
title: Preserve exact catalog removal semantics through provider events
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - events
dependencies:
  - type: blocks
    target: is-01m0t65vgar07vys3fqmqnd0t5
parent_id: is-01m0t5yhbk3cds1j6x33pvaf26
created_at: 2026-08-24T15:28:04.658Z
updated_at: 2026-08-24T15:33:32.715Z
closed_at: 2026-08-24T15:33:32.714Z
close_reason: Updated provider-neutral event projection to construct CatalogChange.remove_files and retain distinct exact-file versus subtree removal semantics; 38 focused catalog/event/wire tests pass.
resolution: null
duplicate_of: null
---
Reconcile src/metabrowser/events.py CatalogChange.remove_files with src/metabrowser/inventory_engine/providers/python.py::_derive_catalog_change and the provider event route. File deletion and gitignored-file upsert use exact remove_files; directory deletion remains subtree removes. Update catalog feed/server tests and constructors without compatibility shims.
