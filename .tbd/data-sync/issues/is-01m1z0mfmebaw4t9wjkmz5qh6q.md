---
type: is
id: is-01m1z0mfmebaw4t9wjkmz5qh6q
title: Prevent stale concurrent refreshes from overwriting newer inventory facts
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T22:43:15.723Z
updated_at: 2026-09-08T00:02:44.047Z
closed_at: 2026-09-08T00:02:44.044Z
close_reason: Refresh observations retain a write generation across threaded filesystem I/O; delayed present and missing observations cannot overwrite newer facts. Both regression variants pass.
resolution: null
duplicate_of: null
---
Python provider refresh permits concurrent watcher and activity calls. _refresh_path invalidates before awaiting lstat but does not check its captured generation afterward, so a slower older observation can overwrite a later refresh, including deleting or resurrecting a file. Reproduce with gated lstat and apply the existing generation-token rule across this await.
