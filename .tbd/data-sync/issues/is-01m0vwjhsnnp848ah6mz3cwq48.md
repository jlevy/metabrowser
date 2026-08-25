---
type: is
id: is-01m0vwjhsnnp848ah6mz3cwq48
title: "PR #74 review 74-9: remove speculative inventory config fields"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:52.980Z
updated_at: 2026-08-25T07:58:59.903Z
closed_at: 2026-08-25T07:58:59.901Z
close_reason: "Fixed: inert cache, traversal, symlink-following, and filesystem-boundary configuration inputs were removed; fixed semantics are documented."
resolution: null
duplicate_of: null
---
Review 5406736360. contract.py exposes traversal and cache_mode although no provider uses them; follow_symlinks and stay_on_filesystem only accept false. Remove speculative fields and update all call sites, docs, fingerprints, tests, and changelog in one internal-contract change.
