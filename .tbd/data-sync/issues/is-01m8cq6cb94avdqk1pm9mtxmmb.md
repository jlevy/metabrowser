---
type: is
id: is-01m8cq6cb94avdqk1pm9mtxmmb
title: Clarify working tree and cloud source behavior in user-facing prompts and design
kind: task
status: closed
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cq5rvmb8jvrvqtqba4r980
hold: null
hold_until: null
created_at: 2026-11-26T20:01:49.368Z
updated_at: 2026-11-26T21:05:07.258Z
started_at: 2026-11-26T20:02:20.757Z
closed_at: 2026-11-26T21:05:07.250Z
close_reason: "Implemented and independently reviewed in merged Metabrowser PR #892. Exact-head CI passed."
resolution: null
duplicate_of: null
---
Working tree means this checkout’s live files and current Git branch. Cloud mode follows the synced branch contents as of the currently served revision.
