---
type: is
id: is-01m774ewjm2x7pmv9g0bv3w26b
title: "PR #361 D2: held restores lose root revalidation and restore priority"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m774evh697aew0sqbs5pe9sn
hold: null
hold_until: null
created_at: 2026-11-12T05:42:31.251Z
updated_at: 2026-11-12T05:53:46.938Z
started_at: 2026-11-12T05:42:40.271Z
closed_at: 2026-11-12T05:53:46.937Z
close_reason: "Fixed in 8fbe7d20: restore start not held; RestoreQueue.putBack and a paused restore; RestorePauseTests."
resolution: null
duplicate_of: null
---
High. AppDelegate.swift:328,332. Review D: https://github.com/jlevy/metabrowser/pull/361#pullrequestreview-5869088038
