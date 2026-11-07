---
type: is
id: is-01m6shhnvfvppa319j426d9cbg
title: Show one PR watch status and resume from reconnect
kind: task
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-06-pr-watch-and-reconnect.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6shhp93hj2aybfj68g5prxh
parent_id: is-01m6shhkwxasd5rpv91y17qc4w
hold: null
hold_until: null
created_at: 2026-11-06T23:01:52.110Z
updated_at: 2026-11-07T02:21:18.649Z
started_at: 2026-11-06T23:03:25.387Z
---
Use one status in Pulls chrome with cached data preserved, a standard progress cue, an actionable Reload control, and automatic retry and recovery on visibility or online changes.

## Notes

Review corrections committed in 67c27fdb. Direct and history filters receive a foreground demand once when visible and incomplete. Background retries retain failure/live text with a trailing delayed spinner. Authentication failures use the hostname-specific command. Focused tests and the slow-provider browser session pass.
