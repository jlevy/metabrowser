---
type: is
id: is-01m1mv9zzrzt294qxymy3bnhfh
title: "PR #101 R3.4: change batches are invalidation-only, so the host re-buys facts"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:44.824Z
updated_at: 2026-09-03T23:57:44.824Z
---
DEFER. One EntryQuery read-back per dirty path plus a second full crossing per merged change because every mutation also dirties DIAGNOSTICS. A 10k-file npm install costs ~50k read-back entries, and a batch that degrades to all_dirty is cheaper than a precise one. An optional bounded facts field on ChangeBatch is additive now and a wire break after release.
