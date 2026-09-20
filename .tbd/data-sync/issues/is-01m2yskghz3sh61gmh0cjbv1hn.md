---
type: is
id: is-01m2yskghz3sh61gmh0cjbv1hn
title: "PR 217 R3: return persisted metadata when concurrent acquisition reuses a store"
kind: bug
status: closed
priority: 1
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yrybwx5zatf3w9chdnfew6
hold: null
hold_until: null
created_at: 2026-09-20T06:56:05.694Z
updated_at: 2026-09-20T07:15:59.984Z
started_at: 2026-09-20T07:00:14.208Z
closed_at: 2026-09-20T07:15:59.981Z
close_reason: "Fixed in 70091d81: reuse returns persisted store/state metadata, not the losing staged revision."
resolution: null
duplicate_of: null
---
src/metabrowser/cache/acquire.py publish_from_staging returns losing staging default_revision when _publish_or_reuse_store reuses an existing store. Reproduced two staged acquisitions straddling a remote commit: race result differs from persisted store/cache hit. Read metadata of the selected store under lock and test this interleaving.

## Notes

Fixed locally in 70091d81 on PR 217; two-stage remote-advance regression passed with acquisition/process/CLI/goldens. Format/lint passed. Push, full gate, CI, and disposition pending. See mb-rldx.
