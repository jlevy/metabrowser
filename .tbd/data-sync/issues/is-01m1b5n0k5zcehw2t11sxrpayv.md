---
type: is
id: is-01m1b5n0k5zcehw2t11sxrpayv
title: Generate JSON Schema for the Git envelopes, with a drift check
kind: task
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies:
  - type: blocks
    target: is-01m1b5n0zs32tdr8rhy1x6wzjc
  - type: blocks
    target: is-01m1b5n1awje3r2enbetszw8kx
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T05:46:07.332Z
updated_at: 2026-08-31T17:19:12.020Z
---
No rewrite and no second declaration: the 31 TypedDicts that exist today stay the declaration.

Verified: pydantic.TypeAdapter(GitRepoInfo).json_schema() emits JSON Schema directly from an existing TypedDict in metabrowser.git.wire. So devtools/build_api_schema.py imports the wire modules, walks their TypedDicts, and writes the output to src/metabrowser/data/api-envelopes/, committed. make lint regenerates and compares.

Pydantic stays out of the runtime path. It is already in [project.dependencies] because diff/format.py and plugin_loader/manifest.py validate documents with it, but this work adds no runtime use: the import is in devtools at generation time and what ships is the JSON Schema. That preserves the current situation where nothing validates a response on the way out -- validate_tree_node is assert-based and invoked from the tests -- which matters because tree and rollup are on the measured load-time path.

One choice to make and record here: TypeAdapter does not set additionalProperties for a TypedDict. Strict is right for a format (it is what diff-model.js enforces as forbidExtras); permissive is right for a reader that should tolerate a field a newer server added. Set it explicitly rather than inheriting a default, and say which and why.
