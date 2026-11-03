---
type: is
id: is-01m6fcnqvqd4h4x0pdh2yk4b5z
title: "PR #280 B2: A .env that is a FIFO, or a symlink to one, blocks the command"
kind: bug
status: closed
priority: 3
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
created_at: 2026-11-03T00:24:18.038Z
updated_at: 2026-11-03T01:06:43.017Z
closed_at: 2026-11-03T01:06:43.016Z
close_reason: "fixed in 54a9000c: skipped unless S_ISREG"
resolution: null
duplicate_of: null
---
Low. dotenv.py:137,142. Review: https://github.com/jlevy/metabrowser/pull/280#pullrequestreview-5745187968
