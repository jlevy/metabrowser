---
type: is
id: is-01m6pgx59g8t2jp6t48c8y95bz
title: Consolidate Pulls catalog status and loading feedback
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-pulls-status
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T18:52:56.494Z
updated_at: 2026-11-05T19:09:24.849Z
started_at: 2026-11-05T18:55:24.202Z
---
Show the repository once in bold, preserve the exact total and display-window context, and use one shared spinner status for Pulls loading and refresh. Keep failure guidance, muted freshness, and shared branch chips. Verify checkout and managed sources with the production browser session and a manual check.

## Notes

Implemented at 5c8cb75b above PR #301. The existing checkout and managed URL were checked in the built-in browser using the public Metabrowser repository. Verified one spinner and one accessible fetch message on cold load, the bold count and repository name, separate PR and mirror freshness, filters, and shared branch chips in the list and PR header. Independent review found that cached Fetch more after a rate limit needed its own activity indication. The existing browserless session reproduced the gap and now covers the fix. Full local gate is running.
