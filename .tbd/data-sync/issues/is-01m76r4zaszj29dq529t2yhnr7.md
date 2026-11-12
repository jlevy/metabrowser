---
type: is
id: is-01m76r4zaszj29dq529t2yhnr7
title: "PR #359 D2: admission is detached from the filesystem object eventually served"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76r4r0pna9p2h3kncd2jp4q
hold: null
hold_until: null
created_at: 2026-11-12T02:07:23.474Z
updated_at: 2026-11-12T03:05:31.297Z
started_at: 2026-11-12T02:58:04.124Z
closed_at: 2026-11-12T03:05:31.296Z
close_reason: "Fixed in 353d3f5e: openat O_NOFOLLOW descriptor walk, same-volume check, re-admission before each background start (RestoreQueue.next(stillOpen:)); residual path-launch race documented. Reply issuecomment-6813151545."
resolution: null
duplicate_of: null
---
High. apps/macos/Sources/Metabrowser/FolderWindows.swift:219 and :269, RootAdmission.swift:16. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867869514.
