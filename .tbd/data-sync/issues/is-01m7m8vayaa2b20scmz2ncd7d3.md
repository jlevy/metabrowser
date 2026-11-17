---
type: is
id: is-01m7m8vayaa2b20scmz2ncd7d3
title: A tree with exactly max_files regular files reports a budget stop
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T08:09:21.098Z
updated_at: 2026-11-17T08:09:21.098Z
---
The Python provider declares truncation when files_indexed >= max_files (python_inventory.py, after the boot walk), so a tree whose regular-file count equals the budget reports stopped, budget coverage, and a resource_budget issue although nothing was left out (confirmed with budgets 2, 3, 4 on a three-file tree: 3 stops). Pinned as it stands by test_provider_budget_counts_regular_files_and_stops_when_they_reach_it (jlevy/metabrowser#508). Decide the rule (a stop only when a file was actually refused) and change provider, test, and contract text together.
