---
type: is
id: is-01m7zxakx0t9ec4qjqr0jt0f1s
title: Update macOS first-run smoke checks for README-based setup
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:38:51.993Z
updated_at: 2026-11-21T20:40:37.237Z
started_at: 2026-11-21T20:40:37.237Z
---
The release smoke script and QA checklist still require inline install commands removed when Settings moved setup help to the README. Update both to verify the current missing, old, pending, and discovered runtime behavior, preserving file-watcher and retry coverage.
