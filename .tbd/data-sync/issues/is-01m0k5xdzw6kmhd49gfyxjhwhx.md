---
type: is
id: is-01m0k5xdzw6kmhd49gfyxjhwhx
title: Record load-time baselines at 10k, 100k, and 1M and replace the proposed budgets
kind: task
status: open
priority: 0
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k4p2s7ay3t761z9da84en0
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:56.827Z
updated_at: 2026-08-21T22:48:27.274Z
---
Run the new page-load phase at 10k, 100k, and 1M against build_corpus, and replace the Proposed Budgets table in the spec with validated ones.

The numbers currently in the spec came from a different corpus, generated outside the repository (pkgNNN/modNNN/fileNNNN.ext, 40 files per leaf, three levels). build_corpus makes 972 directories, wide at the top and deep in one branch, with 64 B to 16 KiB bodies. Expect different absolute numbers. What should survive the change of shape is the relation: usable tree data reaching the browser in hundreds of milliseconds while the first row waits seconds for the scan.

The 1M run needs care: the walker reports status=truncated at INVENTORY_MAX_FILES = 500_000, so record what was actually indexed, not what was on disk.
