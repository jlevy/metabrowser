---
type: is
id: is-01m6shhnakxdd0zeetnvzjrnvx
title: Classify GitHub watch failures and bound catalog recovery
kind: task
status: in_progress
priority: 2
version: 2
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6shhkwxasd5rpv91y17qc4w
hold: null
hold_until: null
created_at: 2026-11-06T23:01:51.567Z
updated_at: 2026-11-06T23:03:25.375Z
started_at: 2026-11-06T23:03:25.375Z
---
Reuse the shared catalog coordinator and incremental provider reads. Distinguish unreachable network, missing gh, sign-in, access, rate limits, and transient failures. Keep cache reads available and honor retry timing.
