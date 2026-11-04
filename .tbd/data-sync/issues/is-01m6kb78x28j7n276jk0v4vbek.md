---
type: is
id: is-01m6kb78x28j7n276jk0v4vbek
title: Replace the retired hosted-review tier in the current Git-source diagram
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:53.121Z
updated_at: 2026-11-04T17:21:01.609Z
closed_at: 2026-11-04T17:21:01.609Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Documentation review D12: the maintained four-layer Git/comparison diagram presents provider adapters as only designed and the retired common Hosted Review Format as an actual tier. Current GitHub integration owns validated plugin records and adapters. Update current diagram/prose to this implemented boundary, retain File Diff Format and the Git process boundary, and label other providers/generic hosted projections as separate research or future work. Do not reintroduce the retired model in code.
