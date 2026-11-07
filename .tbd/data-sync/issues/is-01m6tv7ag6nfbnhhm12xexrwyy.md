---
type: is
id: is-01m6tv7ag6nfbnhhm12xexrwyy
title: Address progressive prefetch startup, revision, and retry findings
kind: task
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6th4qn5b1s27zkw8rw3736h
hold: null
hold_until: null
created_at: 2026-11-07T11:10:12.997Z
updated_at: 2026-11-07T11:10:13.484Z
started_at: 2026-11-07T11:10:13.483Z
---
Review of public pull request324 found the delayed initial catalog race, changed/new prefix rows missed within an epoch, repeated settled not_owner demands, and missing transient retry for unfinished hidden Files work. Use source backoff, pause/resume, exact receipt ownership, and generation-aware cursor state without a timer after completion. Coordinate backend partial receipt semantics. Retain deliberate cache-only focus catch-up. Pin races in concise production-controller sessions.
