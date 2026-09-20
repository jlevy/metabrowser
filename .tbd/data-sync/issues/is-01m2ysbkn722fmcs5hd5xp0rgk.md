---
type: is
id: is-01m2ysbkn722fmcs5hd5xp0rgk
title: "PR 217 R1: preserve SHA-256 object format during acquisition"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yrybwx5zatf3w9chdnfew6
hold: null
hold_until: null
created_at: 2026-09-20T06:51:46.725Z
updated_at: 2026-09-20T06:53:08.429Z
started_at: 2026-09-20T06:53:08.418Z
---
src/metabrowser/cache/acquire.py:290 initializes SHA-1 unconditionally. Reproduced SHA-256 file source failing with mismatched algorithms. Initialize using the validated advertised HEAD object format; add end-to-end coverage.
