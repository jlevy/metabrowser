---
type: is
id: is-01m0nyykn56bc4qzvremnzjn65
title: "H45: replace stdlib json with orjson on the tree and rollup routes"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:58.661Z
updated_at: 2026-11-14T18:41:54.715Z
---
Load-time hypothesis H45 (plan-2026-08-21-load-time-performance.md, Hypotheses). Serialization is a measurable share of large /api/tree and /api/rollup responses, and orjson would show it. Metric: server time on both routes at 300,000 entries. A new dependency follows SUPPLY-CHAIN-SECURITY.md.
