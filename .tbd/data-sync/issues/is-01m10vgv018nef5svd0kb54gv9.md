---
type: is
id: is-01m10vgv018nef5svd0kb54gv9
title: "Repository library Phase 2: catalog, refresh, and cache management"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01m10vgvh4pvre1adnkgm2egp1
  - type: blocks
    target: is-01m10vgw6vhq82cd495kvhh9gf
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:40.448Z
updated_at: 2026-08-27T05:37:05.355Z
---
Scan validated repo.yml records into a correct-by-construction catalog; add list, inspect, coordinated Git and provider refresh, and recoverable purge commands; fetch refs without mutating the active gitroot; stage replacement checkouts and promote only outside live sessions; report stage-level progress and partial failures; measure size and age before selecting any automatic eviction policy.
