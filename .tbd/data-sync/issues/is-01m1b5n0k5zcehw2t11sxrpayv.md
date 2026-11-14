---
type: is
id: is-01m1b5n0k5zcehw2t11sxrpayv
title: Generate JSON Schema for the Git envelopes, with a drift check
kind: task
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies:
  - type: blocks
    target: is-01m1b5n0zs32tdr8rhy1x6wzjc
  - type: blocks
    target: is-01m1b5n1awje3r2enbetszw8kx
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T05:46:07.332Z
updated_at: 2026-11-14T18:46:47.086Z
---
Phase 1 of the plan, scoped to /api/git/*. The TypedDicts in metabrowser.git.wire stay the declaration: no rewrite and no second declaration. pydantic.TypeAdapter(GitRepoInfo).json_schema() emits JSON Schema from them directly (rechecked 2026-11-14). devtools/build_api_schema.py imports the wire modules, walks their TypedDicts, and writes the output to src/metabrowser/data/api-envelopes/, committed; make lint regenerates and compares.

Pydantic stays out of the runtime path. It is already in [project.dependencies] because diff/format.py and plugin_loader/manifest.py validate documents with it, but this work adds no runtime use: the import is in devtools at generation time and what ships is the JSON Schema. Nothing validates a response on the way out today (validate_tree_node is assert-based and invoked from the tests), which matters because tree and rollup are on the measured load-time path.

TypeAdapter sets no additionalProperties, and the plan needs two values: permissive for the served schema, so a reader tolerates a field a newer server adds, and strict for golden validation (mb-qdr1), which a permissive schema would pass by construction. Emit both, or one schema with a documented strict overlay, and record the choice.
