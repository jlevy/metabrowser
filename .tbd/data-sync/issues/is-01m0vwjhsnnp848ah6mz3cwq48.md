---
type: is
id: is-01m0vwjhsnnp848ah6mz3cwq48
title: "PR #74 review 74-9: remove speculative inventory config fields"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:52.980Z
updated_at: 2026-08-25T07:18:52.980Z
---
Review 5406736360. contract.py exposes traversal and cache_mode although no provider uses them; follow_symlinks and stay_on_filesystem only accept false. Remove speculative fields and update all call sites, docs, fingerprints, tests, and changelog in one internal-contract change.
