---
type: is
id: is-01m1mva0nyrz9m77r1ab7jexhc
title: "PR #101 R3.6: provider-internal modules live outside providers/"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:45.533Z
updated_at: 2026-09-03T23:57:45.533Z
---
walker.py and watch_backends.py are provider implementation detail (their own docstrings say so) living outside providers/ and importing the contract. test_inventory_provider_ownership checks who imports the provider but not what provider-internal code lives outside it; the reverse check would have caught R2b and R2c structurally.
