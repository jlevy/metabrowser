---
type: is
id: is-01kzz02ks9eygwfy31je8z907v
title: Implement Registry v1 source, typed loader, and validator
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - registry
  - python
dependencies:
  - type: blocks
    target: is-01kzz02zvd18eqbqqqrnssr2qj
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:02:06.504Z
updated_at: 2026-08-14T02:26:35.756Z
closed_at: 2026-08-14T02:26:35.742Z
close_reason: Implemented the packaged Registry v1 TOML, immutable cached loader, stable validation errors and fingerprint, registry projection, and compatibility facade; focused registry, inventory, lint, and type checks pass.
---
Add the packaged src/metabrowser/data/file-types.toml reference source and src/metabrowser/file_type_registry.py immutable group, family, kind, registry, match, and classification types. Implement load_file_type_registry(), normalized fingerprinting, fail-fast validation, package-data inclusion, and one cached process-wide instance. Refactor file_type_filters.py into a compatibility facade derived from the registry. Tests: valid source, every validation error code, ordering, normalized fingerprint stability, package/wheel inclusion, and no request-path parsing. Acceptance: registry fields and behavior match Registry v1; current public taxonomy helpers remain additive and compatible.
