---
type: is
id: is-01m6hsvza8q7xmwa5q6m892kc9
title: Use catalog response identity without per-page authentication probes
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hryve021ndx04tt967a6a9
hold: null
hold_until: null
created_at: 2026-11-03T22:53:22.630Z
updated_at: 2026-11-03T22:53:30.780Z
started_at: 2026-11-03T22:53:30.780Z
---
Keep one active-account check per catalog job and attribute every GraphQL page to its authoritative viewer.login and repository identity. Remove the redundant post-page gh auth status call, which official gh source shows performs HTTP work. Preserve page CAS, account-separated checkpoints, rate holds and cache-only reads. Explicitly accept a completed response under its original reader after local account settings change; reject a later page from a different viewer without mixing rows. Add focused ordered-call, retention and stale-publisher controls; retain the superseded external guard probe as evidence. No token/config parsing, wrapper, quota or latency claim. Coordinator owns commit and publication.
