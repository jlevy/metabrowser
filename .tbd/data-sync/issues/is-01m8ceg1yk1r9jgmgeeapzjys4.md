---
type: is
id: is-01m8ceg1yk1r9jgmgeeapzjys4
title: Speed up the local development loop
kind: task
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/889
    at: 2026-11-26T19:07:49.142Z
delegate: claude-code@vm
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T17:29:49.266Z
updated_at: 2026-11-26T19:07:49.143Z
started_at: 2026-11-26T18:01:36.731Z
---
Straightforward wins found while building the merge readiness stack (mb-u16j): golden updates for a subset of files, a tryscript runner that works outside make, the UV_NATIVE_TLS warning kept out of goldens, root-only tests skipped when running as root, golden and pytest parallelism matched to the machine, a fast affected-tests target, and a tested environment setup script that installs a Git at or above the floor. Goldens that print whole status objects are tracked separately.

## Notes

Committed on claude/eloquent-lamport-tjn26f-dev-loop (not yet pushed; the push was refused by this session's permission system): 6d8c45360 build: run tryscript through one script and regenerate only named goldens; c22a0fa72 test: skip the tests that stage a mode refusal when root runs them; fdc6b7259 test: keep the kept-answer status test independent of an ambient GH_TOKEN. Skipped: GOLDEN_JOBS from nproc and pytest workers (already one per processor here and in CI), test-changed (a name-mention heuristic misleads). Environment setup script for Git >= floor prepared outside the repository.
