---
type: is
id: is-01m6fcnp48mcc064g4nz4sfwj1
title: "PR #280 A11: What could leave the eager tier"
kind: bug
status: open
priority: 3
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
created_at: 2026-11-03T00:24:16.263Z
updated_at: 2026-11-03T01:06:46.165Z
---
Low suggestion. static/perf.js and the startup budget. Review: https://github.com/jlevy/metabrowser/pull/280#pullrequestreview-5745158740

## Notes

Deferred from review A on PR #280. Waiting on the measurement docs/development.md asks of a tier change: static/perf.js is the candidate, 12,196 B gzipped, third largest eager script. Startup was 179,434 B, 277 B under the budget, at 454a509e.
