---
type: is
id: is-01m03v2hywswp11fx1ccq7dhzd
title: Prefetch subfolder listings so tree expansion is instant
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-08-15T23:10:53.890Z
updated_at: 2026-08-16T00:08:21.355Z
closed_at: 2026-08-16T00:08:21.354Z
close_reason: null
---
Expanding a folder in a large tree briefly shows a loading spinner. Subfolder listings a user might expand should generally be prefetched by the time they click, so expansion renders instantly with no loading state at all in the common case.
