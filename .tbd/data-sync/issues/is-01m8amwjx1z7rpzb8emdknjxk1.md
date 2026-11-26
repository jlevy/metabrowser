---
type: is
id: is-01m8amwjx1z7rpzb8emdknjxk1
title: "softschema plugin: folder table source, collection index cache, overview and record view"
kind: feature
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: branch
    url: https://github.com/jlevy/metabrowser/tree/codex/softschema-folder-tables
    at: 2026-11-26T17:55:35.181Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwhv15ckjw7prckfmmggr
hold: null
hold_until: null
created_at: 2026-11-26T00:43:02.432Z
updated_at: 2026-11-26T17:55:37.709Z
started_at: 2026-11-26T17:54:36.329Z
---
Phase 3: fixture collection with every bad-record kind; core folder table source (offer, directory TableHandle, table query key, indexing page reason); builtin_plugins/softschema over the upstream API with a SQLite index in the plugin cache and a single-flight builder; references from learned ID prefixes; collection route; overview and SoftSchema record view; goldens, parity rows, map, changelog.

## Notes

Published preview branch works against the unreleased SoftSchema collection API in PR #78. Universe yielded 4,971 valid records and 18 tables; Patch the Conference yielded 132 valid records and 9 tables. Tests cover source links, cross-folder relationship filters, and stable generations. Full rollout still needs the released API, the complete collection and record-detail UX, and final parity.
