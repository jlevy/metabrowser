---
type: is
id: is-01m1b5n0k5zcehw2t11sxrpayv
title: Generate JSON Schema from the wire TypedDicts, with a drift check
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies: []
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T05:46:07.332Z
updated_at: 2026-08-31T05:46:07.332Z
---
devtools/build_api_schema.py walks wire_models.py and git/wire.py and emits one JSON Schema per envelope into src/metabrowser/data/api-envelopes/. The output is committed and a make lint check regenerates and compares, the way compiled-schema drift is checked for the cache contracts. Derive, never duplicate: a hand-written second copy is the drift this avoids.
