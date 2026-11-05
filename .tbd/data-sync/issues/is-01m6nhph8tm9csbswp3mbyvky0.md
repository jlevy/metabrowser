---
type: is
id: is-01m6nhph8tm9csbswp3mbyvky0
title: Keep a prepared PR readable when an unrelated visible summary changes
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6mwzwzd4jmbe0jbpxqpep3j
hold: null
hold_until: null
created_at: 2026-11-05T09:47:33.529Z
updated_at: 2026-11-05T09:47:34.006Z
started_at: 2026-11-05T09:47:34.005Z
---
H83, from exp-053 on PR #301: live catalog generation changed only the indexed member for #300, invalidating all three stable #294 prepared reads. Keep exact full-cohort admission and viewer/repository proof, then validate each member for publication, cache read, and adoption. Hold both race interleavings and repeat the installed comparison with live catalog update.
