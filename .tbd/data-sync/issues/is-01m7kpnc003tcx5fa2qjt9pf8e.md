---
type: is
id: is-01m7kpnc003tcx5fa2qjt9pf8e
title: "CI speed 2.2: add devtools/check_ci.py to make lint-check, so the workflow cannot silently drop a tier, a shard, or an interpreter"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:31.199Z
updated_at: 2026-11-17T02:51:31.199Z
---
Phase 2 of plan-2026-11-16-fast-ci.md, How Coverage Is Kept. Fails unless ci.yml runs each of test-parallel, test-serial, and test-goldens; the shard numbers of each sharded job are 1 through N; the interpreters match pyproject.toml's classifiers and the free-threaded build; and a push to main runs the serial tier on all of them. devtools/check_supply_chain.py already holds the admitted-git matrix to both Git floors.
