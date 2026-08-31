---
type: is
id: is-01m1cd5w5mknpj3h65ccxakx57
title: "PR #90 PLAN-02: The tree and rollup TypedDicts are deliberately vacuous, so the schema is empty"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1cd5vdf1q8c3mj15at60znc
created_at: 2026-08-31T17:16:54.323Z
updated_at: 2026-08-31T17:29:10.647Z
closed_at: 2026-08-31T17:29:10.647Z
close_reason: "Fixed in 501b31b; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
Verified: TypeAdapter(DirNode).json_schema() emits required=(none) because total=False, and children as {"items": {}} -- unconstrained. The generated schema is empty exactly where the plan locates the risk. "Nothing is rewritten" and "a meaningful tree schema" are mutually exclusive; the plan must pick one.
