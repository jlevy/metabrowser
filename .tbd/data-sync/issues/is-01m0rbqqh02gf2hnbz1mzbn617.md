---
type: is
id: is-01m0rbqqh02gf2hnbz1mzbn617
title: Migrate tree and navigation queries to coherent provider reads
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqsb3e5ep9c328y6ybk4z
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:53.599Z
updated_at: 2026-08-23T22:26:55.458Z
---
Files: refactor src/metabrowser/tree.py and server.py api_tree, _ensure_inventory_serving and shell initial-tree paths; update tests/test_browser_inventory_api.py, test_tree_filter.py, test_initial_tree_inline.py, navigation-tally tests and related browser goldens. Functions: make tree builders pure over provider-neutral snapshots; remove parent_is_gitignored, inventory_has_data and inventory_status singleton lookups; compose DirectoryQuery, FilteredTreeQuery and NavigationQuery in one ReadRequest; preserve cold-start grace, progressive shallow rows, filter totals, lazy boundaries, gitignore propagation, logical extensions and tally staleness behavior. Acceptance: every payload field and polling state matches current behavior, one read result supplies its own version/state/work record, and route code neither imports nor samples a concrete provider.
