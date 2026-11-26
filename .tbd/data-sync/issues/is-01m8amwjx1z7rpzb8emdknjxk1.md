---
type: is
id: is-01m8amwjx1z7rpzb8emdknjxk1
title: "softschema plugin: folder table source, collection index cache, overview and record view"
kind: feature
status: in_progress
priority: 2
version: 18
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
  - is-01m8cna41ywe1mr8tdpade6jb1
  - is-01m8cnf3htjx8gp16bqgxjxjdw
  - is-01m8cnf48z3vjgkfbxsv2kpstt
  - is-01m8cnf4sgyjn4q4psvp77emx2
  - is-01m8cst8y0jqwef2tg9smftat0
hold: null
hold_until: null
created_at: 2026-11-26T00:43:02.432Z
updated_at: 2026-11-26T20:47:38.424Z
started_at: 2026-11-26T17:54:36.329Z
---
Phase 3: fixture collection with every bad-record kind; core folder table source (offer, directory TableHandle, table query key, indexing page reason); builtin_plugins/softschema over the upstream API with a SQLite index in the plugin cache and a single-flight builder; references from learned ID prefixes; collection route; overview and SoftSchema record view; goldens, parity rows, map, changelog.

## Notes

The bounded in-memory preview is verified through the real Universe table routes. First-phase coverage, detail, and released-dependency rollout have separate beads. The later schema catalog, disk projection, row-level refresh, and 100K-to-millions continuous scrolling are planned under separate child beads.
