---
type: is
id: is-01m12cvt41r4t6p4hzw2re3v1j
title: "PR #86 review R3: exception in reap_expired kills the reaper task"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:00.224Z
updated_at: 2026-08-27T19:59:00.224Z
---
src/metabrowser/git/history.py:881. _reap_loop handles only CancelledError; an OSError from session.close() ends the task and idle sessions leak until process exit. Wrap and log. PR #86 comment 3873346513
