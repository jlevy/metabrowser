---
type: is
id: is-01m0k5xha8rmnc747e64g6a5wa
title: "Replace INVENTORY_MAX_FILES = 500_000: no silent truncation at any size"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:09:00.232Z
updated_at: 2026-08-21T22:48:51.499Z
---
A million-file folder is not slow today, it is absent: the walker reports status=truncated files=500000 and half the corpus never appears. INVENTORY_MAX_FILES = 500_000 lives in src/metabrowser/settings.py, surfaced through walker.py as DEFAULT_MAX_FILES.

Two options, and the choice needs mb-migx's measurement first, because a cap is a claim about cost and there is no measurement of that cost yet: a higher measured cap, or a progressive index with no cap and a visible frontier. Silent truncation is not an option either way -- see 'degrade visibly' in docs/large-content-rendering.md.

Observable either way, so it lands in CHANGELOG.md and in docs/project/architecture/arch-state-and-delivery.md.
