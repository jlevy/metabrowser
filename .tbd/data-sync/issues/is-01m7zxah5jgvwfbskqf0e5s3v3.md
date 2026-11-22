---
type: is
id: is-01m7zxah5jgvwfbskqf0e5s3v3
title: Include shared native bundle inputs in macOS release provenance
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
created_at: 2026-11-21T20:38:49.263Z
updated_at: 2026-11-21T20:40:37.225Z
started_at: 2026-11-21T20:40:37.225Z
---
The macOS build copies the shared Lucide glyph license from outside apps/macos; an uncommitted edit can currently go into a signed app stamped with a clean commit. Check the native packaging inputs consistently before the build and when stamping its source. Add a regression for changes to the shared file.
