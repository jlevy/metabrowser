---
type: is
id: is-01m7n8arwwxqq83hsf7mm7m403
title: "PR view and Pulls: every drawn element is persisted on disk and painted from it first"
kind: task
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
hold: null
hold_until: null
created_at: 2026-11-17T17:19:32.763Z
updated_at: 2026-11-17T17:21:41.825Z
started_at: 2026-11-17T17:21:41.824Z
---
Inventory each element the PR view and Pulls nav draw from fetched data (file list, per-file totals, change summary, checks, reviews, stack info, avatars, ...): persisted on disk or not, where, and whether a cold or reopened view paints it from disk before any network call. Fix gaps. Prefer a check: a test that asserts each drawn element's route answers from the disk cache with the network stubbed out.
