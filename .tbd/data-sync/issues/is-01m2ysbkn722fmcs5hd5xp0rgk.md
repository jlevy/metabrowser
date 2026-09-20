---
type: is
id: is-01m2ysbkn722fmcs5hd5xp0rgk
title: "PR 217 R1: preserve SHA-256 object format during acquisition"
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
created_at: 2026-09-20T06:51:46.725Z
updated_at: 2026-09-20T07:15:58.990Z
started_at: 2026-09-20T06:53:08.418Z
closed_at: 2026-09-20T07:15:58.989Z
close_reason: "Fixed in 70091d81: staging init uses the advertised object format."
resolution: null
duplicate_of: null
---
src/metabrowser/cache/acquire.py:290 initializes SHA-1 unconditionally. Reproduced SHA-256 file source failing with mismatched algorithms. Initialize using the validated advertised HEAD object format; add end-to-end coverage.

## Notes

Fixed locally in 70091d81 on PR 217; acquisition/process/CLI/golden selection: 44 passed, one skipped. Format/lint passed. Restacked into PR 216. Push, full gate, CI, and disposition pending. See mb-rldx.
