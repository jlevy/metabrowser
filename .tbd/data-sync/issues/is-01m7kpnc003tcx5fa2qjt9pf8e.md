---
type: is
id: is-01m7kpnc003tcx5fa2qjt9pf8e
title: "CI speed 2.2: add devtools/check_ci.py to make lint-check, so the workflow cannot silently drop a tier, a shard, or an interpreter"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:31.199Z
updated_at: 2026-11-17T04:07:46.282Z
---
Phase 2 of plan-2026-11-16-fast-ci.md, How Coverage Is Kept. Fails unless ci.yml runs each of test-parallel, test-serial, test-chrome, and test-goldens, and test-serial on every interpreter (review A1 of #496); the shard numbers of each sharded job are 1 through N; every interpreter list in ci.yml (the unit and goldens matrices and the plan job's PYTHONS) matches pyproject.toml's classifiers and the free-threaded build, and PR_CHROME_PYTHON is one of them (review A5); and the chrome matrix is the plan job's chrome-pythons output. ci_plan.sh's own tests hold that a push to main, and a pull request while main is red, get all of PYTHONS. devtools/check_supply_chain.py already holds the admitted-git matrix to both Git floors.
