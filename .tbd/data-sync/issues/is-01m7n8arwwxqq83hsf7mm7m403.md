---
type: is
id: is-01m7n8arwwxqq83hsf7mm7m403
title: "PR view and Pulls: every drawn element is persisted on disk and painted from it first"
kind: task
status: closed
priority: 1
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/528
    at: 2026-11-20T17:02:26.932Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/530
    at: 2026-11-20T17:02:26.973Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/533
    at: 2026-11-20T17:02:26.973Z
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
hold: null
hold_until: null
created_at: 2026-11-17T17:19:32.763Z
updated_at: 2026-11-20T17:59:59.998Z
started_at: 2026-11-17T17:21:41.824Z
closed_at: 2026-11-18T04:44:14.087Z
close_reason: "Landed in #528 (1c06d4635). Gap 3 is fixed by #530 and gap 2 by #533, both queued with the coordinator. Gap 1 (avatars) is left for the owner and stays a strict xfail."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: fe805e98-e407-4c26-9474-d8541f63774e
    linked_at: 2026-11-20T17:59:59.987Z
---
Inventory each element the PR view and Pulls nav draw from fetched data (file list, per-file totals, change summary, checks, reviews, stack info, avatars, ...): persisted on disk or not, where, and whether a cold or reopened view paints it from disk before any network call. Fix gaps. Prefer a check: a test that asserts each drawn element's route answers from the disk cache with the network stubbed out.
