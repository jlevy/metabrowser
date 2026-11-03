---
type: is
id: is-01m6fcnqcv988h918y3kf5rdh9
title: "PR #280 B1: A dotenv file's parse is unbounded"
kind: bug
status: closed
priority: 1
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
created_at: 2026-11-03T00:24:17.562Z
updated_at: 2026-11-03T01:06:42.699Z
closed_at: 2026-11-03T01:06:42.698Z
close_reason: "fixed in 54a9000c: 64 KB cap with the measurement beside it, interpolation off"
resolution: null
duplicate_of: null
---
Medium. dotenv.py:137-143: quadratic through interpolation, no size cap. Review: https://github.com/jlevy/metabrowser/pull/280#pullrequestreview-5745187968
