---
type: is
id: is-01m8amwjx1z7rpzb8emdknjxk1
title: "softschema plugin: folder table source, collection index cache, overview and record view"
kind: feature
status: in_progress
priority: 2
version: 12
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: branch
    url: https://github.com/jlevy/metabrowser/tree/codex/softschema-folder-tables
    at: 2026-11-26T17:55:35.181Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwhv15ckjw7prckfmmggr
child_order_hints:
  - is-01m8cn7n1bbgy9zg7smznv96ec
  - is-01m8cn7nq8m5dye6fazv28kz21
  - is-01m8cn7pfer7dn5f1em8t8xhv8
  - is-01m8cn7q1vmcb79egjcc9bqp7f
  - is-01m8cn7qmjcfyf6gzgk54se1fe
  - is-01m8cn7rkh3hmx5phmv0f35nf1
hold: null
hold_until: null
created_at: 2026-11-26T00:43:02.432Z
updated_at: 2026-11-26T19:27:37.584Z
started_at: 2026-11-26T17:54:36.329Z
---
Phase 3: fixture collection with every bad-record kind; core folder table source (offer, directory TableHandle, table query key, indexing page reason); builtin_plugins/softschema over the upstream API with a SQLite index in the plugin cache and a single-flight builder; references from learned ID prefixes; collection route; overview and SoftSchema record view; goldens, parity rows, map, changelog.

## Notes

Published preview: indexed 132 Patch the Conference records into 9 tables and 4,971 Universe records into 18 tables. Verified browser keyboard navigation and source links, schema help, incremental refresh, and exact cross-folder relationship filters. Both Metabrowser prerequisite PRs landed. Full folder rollout still requires the released SoftSchema collection API and remaining record-detail work.
