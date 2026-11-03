---
type: is
id: is-01m6fcnqcv988h918y3kf5rdh9
title: "PR #280 B1: A dotenv file's parse is unbounded"
kind: bug
status: open
priority: 1
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
created_at: 2026-11-03T00:24:17.562Z
updated_at: 2026-11-03T00:24:17.562Z
---
Medium. dotenv.py:137-143: quadratic through interpolation, no size cap. Review: https://github.com/jlevy/metabrowser/pull/280#pullrequestreview-5745187968
