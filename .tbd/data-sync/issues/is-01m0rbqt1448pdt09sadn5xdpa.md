---
type: is
id: is-01m0rbqt1448pdt09sadn5xdpa
title: Prove complete behavior preservation and provider contract coverage
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqtbt3mjghbxhcryzjewp
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:56.163Z
updated_at: 2026-08-24T02:58:51.953Z
closed_at: 2026-08-24T02:58:51.952Z
close_reason: Provider contract, route/SSE preservation, ownership, concurrency, lifecycle, watcher, and deterministic partial-coverage tests pass; make verify succeeds with 1495 tests and 48 golden scenarios.
resolution: null
duplicate_of: null
---
Files: add or extend provider-parameterized contract tests, normalized route/SSE goldens, semantic digest fixtures and concurrency tests across tests/test_inventory_provider_contract.py plus existing browser inventory suites. Scenarios: complete/progressive/partial/truncated/failed roots; ignored files; symlinks; compound extensions; mutation during reads and baseline discovery; queue overflow/reset/resume; cancellation/root replacement; catalog paging; active overlays; validator atomicity. Acceptance: each row of the plan preservation matrix has an explicit test, deterministic bounds/work assertions run in CI, existing DOM/plugin/wire tests stay green, and make verify passes with no wall-clock threshold.
