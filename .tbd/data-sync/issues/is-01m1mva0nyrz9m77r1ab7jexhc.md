---
type: is
id: is-01m1mva0nyrz9m77r1ab7jexhc
title: "PR #101 R3.6: provider-internal modules live outside providers/"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md
labels: []
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-09-03T23:57:45.533Z
updated_at: 2026-11-14T18:44:31.170Z
---
walker.py and watch_backends.py are provider implementation detail (their own docstrings say so) living outside providers/ and importing the contract. test_inventory_provider_ownership checks who imports the provider but not what provider-internal code lives outside it; the reverse check would have caught R2b and R2c structurally.
