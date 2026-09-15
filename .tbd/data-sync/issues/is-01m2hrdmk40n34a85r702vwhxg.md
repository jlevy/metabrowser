---
type: is
id: is-01m2hrdmk40n34a85r702vwhxg
title: Keep the flat-stress budget file from drifting off the release gate
kind: task
status: open
priority: 2
version: 2
labels:
  - performance
dependencies: []
parent_id: is-01m2hs64m7nfagfxyf7b0hxrhr
created_at: 2026-09-15T05:25:17.028Z
updated_at: 2026-09-15T05:38:48.209Z
---
`explorations/performance-loop/performance-budgets-flat-stress.toml` is the release
gate's file with one declared divergence (`first_row_ms` 350 -> 450). The loader takes no
inheritance, so it is a standalone copy, and nothing stops the two drifting apart.

Today the relationship is stated in the stress file's header and verified by hand.
AGENTS.md prefers a check to a sentence, so this should be a check: assert that the two
files' `[requirements]` tables are equal and that their `[metrics]` tables differ only in
the keys the stress file's header declares.

Done when: a check enforces it and fails on an undeclared divergence in either direction.
