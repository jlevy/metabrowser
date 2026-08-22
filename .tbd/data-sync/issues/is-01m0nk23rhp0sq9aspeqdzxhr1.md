---
type: is
id: is-01m0nk23rhp0sq9aspeqdzxhr1
title: Walk tracked files before ignored ones (H33)
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:37:10.531Z
updated_at: 2026-08-22T20:37:10.531Z
---
Perceived-performance change requested by the maintainer, not a pure optimization. Ignored subtrees (node_modules, .venv, build output, caches) are usually the bulk of a real tree and the least interesting: on the trading tree os.walk sees 720,951 files where the walker indexes 241,063, and much of the remainder is ignored or dot-directories. Crawl everything -- flags still control what is revealed -- but order the frontier so tracked entries are discovered and published first and ignored ones fill in behind them. The reader then gets a usable tree in a fraction of the total scan. Interacts with the level-order guarantee the walker documents (shallow dirs finalize first), so the ordering policy needs to compose rather than replace it. Metrics: time until all TRACKED entries are indexed, vs total walk; first_row_ms unchanged or better.
