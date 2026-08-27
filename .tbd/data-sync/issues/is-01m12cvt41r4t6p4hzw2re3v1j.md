---
type: is
id: is-01m12cvt41r4t6p4hzw2re3v1j
title: "PR #86 review R3: exception in reap_expired kills the reaper task"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:00.224Z
updated_at: 2026-08-27T20:21:16.961Z
closed_at: 2026-08-27T20:21:16.961Z
close_reason: "Fixed in 3ad9113 on codex/unbounded-git-history (PR #86)"
resolution: null
duplicate_of: null
---
src/metabrowser/git/history.py:881. _reap_loop handles only CancelledError; an OSError from session.close() ends the task and idle sessions leak until process exit. Wrap and log. PR #86 comment 3873346513
