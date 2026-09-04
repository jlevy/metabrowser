---
type: is
id: is-01m1mv982mzbg61fnp4gnzcstg
title: "PR #101 R5a: MtimeCache.delete resolves before checking membership"
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:20.339Z
updated_at: 2026-09-04T02:07:13.076Z
closed_at: 2026-09-04T02:07:13.075Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
mtime_cache.py:126 calls path.resolve() (the syscall being counted) before checking membership. Both caches are LRUCache(maxsize=256), so nearly every invalidation resolves a path that was never cached. An early return removes the same 45,516 resolves with no semantic change and no reliance on the DISCOVERING phase gate.
