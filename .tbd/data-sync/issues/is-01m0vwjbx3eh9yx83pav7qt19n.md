---
type: is
id: is-01m0vwjbx3eh9yx83pav7qt19n
title: "PR #74 review 74-3: seal PythonInventoryHandle behind the five-method contract"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:46.938Z
updated_at: 2026-08-25T07:18:46.938Z
---
Review 5406736360. python_inventory.py retains 27 public legacy accessors beyond read, changes, refresh, prioritize, close. Split store/projection internals where useful or make all non-contract methods private, and migrate behavior tests to contract reads.
