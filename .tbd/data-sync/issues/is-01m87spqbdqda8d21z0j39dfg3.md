---
type: is
id: is-01m87spqbdqda8d21z0j39dfg3
title: Bound the cache's size beyond the free-space reserve
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
created_at: 2026-11-24T22:09:29.962Z
updated_at: 2026-11-24T22:09:29.962Z
---
Threat model T11. Stores and pull-request records are never evicted (cache/reclaim.py deletes only staging); the only bound is FREE_SPACE_RESERVE_MB. Decide an eviction policy for stores and records, and give the PDF preview area its measured bound (mb-7tcl).
