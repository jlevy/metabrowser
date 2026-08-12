---
type: is
id: is-01kzt7xnav8ahwtsvwrw73q4s2
title: "PR #32 review MB32-R5: assess event-loop snapshot cost"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzt7x3qqb7y2qgpbxhjg3k3x
created_at: 2026-08-12T05:43:00.698Z
updated_at: 2026-08-12T05:50:13.359Z
closed_at: 2026-08-12T05:50:13.358Z
close_reason: "Rebutted/no code change: the event-loop list snapshot is intentional to avoid iterating a mutating inventory off-thread, is bounded by the 500,000-file inventory cap, and the review explicitly classifies it as informational with no action needed."
---
PR #32 senior review MB32-R5 (Info). src/metabrowser/server.py api_tree. Validate the full-index list snapshot on the event loop and record an explicit disposition; the review recommends no code change.
