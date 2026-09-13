---
type: is
id: is-01m1dt4108x52mm36zeejjga19
title: No performance run has ever recorded an inventory provider
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-09-01T06:22:19.655Z
updated_at: 2026-09-13T21:36:43.656Z
closed_at: 2026-09-13T21:36:43.655Z
close_reason: exp-031 and exp-032 record inventory_provider=python and inventory_contract=inventory-provider-v1 for every candidate run on the refactored engine, with v0.9.1 controls; the premise that no run records a provider no longer holds.
resolution: null
duplicate_of: null
---
All 197 rows in explorations/performance-loop/results/runs.jsonl have inventory_provider = null. The provider identity fields were added to the harness by the inventory refactor but no run has been recorded on the refactored engine, so the performance loop has no evidence for or against it.

The refactor is behaviour-preserving by intent and turned out to be 2.75x slower on a 60k corpus (mb-0y68), which a recorded run would have caught. Record a candidate/release pair on the merged stack once mb-0y68 and mb-tprh land, so the provider swap has a baseline to be measured against when fdu arrives.
