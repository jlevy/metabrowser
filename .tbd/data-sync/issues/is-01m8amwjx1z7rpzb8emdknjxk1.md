---
type: is
id: is-01m8amwjx1z7rpzb8emdknjxk1
title: "softschema plugin: folder table source, collection index cache, overview and record view"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies: []
parent_id: is-01m8amwhv15ckjw7prckfmmggr
created_at: 2026-11-26T00:43:02.432Z
updated_at: 2026-11-26T10:45:17.680Z
---
Phase 3: fixture collection with every bad-record kind; core folder table source (offer, directory TableHandle, table query key, indexing page reason); builtin_plugins/softschema over the upstream API with a SQLite index in the plugin cache and a single-flight builder; references from learned ID prefixes; collection route; overview and SoftSchema record view; goldens, parity rows, map, changelog.

## Notes

Preview work is on codex/softschema-folder-tables. The shared table source reads the Paraverse collection of 132 records and 9 contracts using the upstream API branch. The released SoftSchema dependency does not yet supply the API.
