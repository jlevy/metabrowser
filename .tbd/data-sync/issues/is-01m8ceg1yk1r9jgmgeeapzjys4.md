---
type: is
id: is-01m8ceg1yk1r9jgmgeeapzjys4
title: Speed up the local development loop
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@vm
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T17:29:49.266Z
updated_at: 2026-11-26T18:01:36.731Z
started_at: 2026-11-26T18:01:36.731Z
---
Straightforward wins found while building the merge readiness stack (mb-u16j): golden updates for a subset of files, a tryscript runner that works outside make, the UV_NATIVE_TLS warning kept out of goldens, root-only tests skipped when running as root, golden and pytest parallelism matched to the machine, a fast affected-tests target, and a tested environment setup script that installs a Git at or above the floor. Goldens that print whole status objects are tracked separately.
