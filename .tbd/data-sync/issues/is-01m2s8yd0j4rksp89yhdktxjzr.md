---
type: is
id: is-01m2s8yd0j4rksp89yhdktxjzr
title: Reclaim unreferenced stores when the cache opens
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
  - stack:pr149
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T03:28:44.562Z
updated_at: 2026-09-18T03:33:07.827Z
started_at: 2026-09-18T03:28:47.300Z
---
Wire reclaim of published stores no alias names into open_cache, after the staging/trash sweep. reclaim_store already exists and is lease-aware: a live exclusive-maintenance busy skip protects a concurrent publish. Read routes still do not sweep, so the populated-home click store stays visible on /api/cache/stores until a write path opens the cache.

Pin: leftover unreferenced store is gone after --no-serve of another origin; a referenced store survives; a leased store is skipped. Pytest in-process golden (same floor monkeypatch as acquire goldens). No serving. No CI Git pin.

## Notes

PR https://github.com/jlevy/metabrowser/pull/149 on cursor/v011-cache-orphan-reclaim-bd04 HEAD 2640ed12, stacked on #148. open_cache reclaims published stores no alias names after the staging/trash sweep. Live lease still skips. Read routes still do not reclaim. Pytest golden cli-cache-orphan-reclaim.txt. Do not close until review.
