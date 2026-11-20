---
type: is
id: is-01kxnx9wyz9tb4yttg2rp3nrf3
title: Prove large-directory startup and interaction budgets
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels:
  - performance
  - scalability
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-07-16T16:49:06.015Z
updated_at: 2026-11-20T19:15:57.110Z
extensions: {}
---
Record reproducible budgets at 100k and 1M entries beyond page load: Quick File search over the catalog, memory (server RSS and client heap), and live-update latency. The synthetic corpus generator exists (build_corpus in devtools/bench_serving.py), explorations/performance-loop/performance-budgets.toml and performance-budgets-flat-stress.toml are the gated budgets, and mb-o2hk records the page-load baselines at 10k, 100k and 1M. CI may use a smaller deterministic gate while a documented benchmark captures the full-scale claim.
