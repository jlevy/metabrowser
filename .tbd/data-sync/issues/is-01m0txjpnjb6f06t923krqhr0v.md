---
type: is
id: is-01m0txjpnjb6f06t923krqhr0v
title: "PR #74 review MB74-C1: refresh stale FDU design references"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0txhaybmj82ym2wcm85zz0b
created_at: 2026-08-24T22:17:12.113Z
updated_at: 2026-08-24T22:25:27.843Z
---
Source: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5401198953. The adoption plan references at docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md:459 and the PR #74 Documents section pin FDU snapshots that predate PR #47's current design and R1-R10 work. Repoint durable context to the live PR #47 design/head and name fdu-u7vo as the live execution map without copying its mutable state.
