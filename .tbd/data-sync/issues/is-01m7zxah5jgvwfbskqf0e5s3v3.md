---
type: is
id: is-01m7zxah5jgvwfbskqf0e5s3v3
title: Include shared native bundle inputs in macOS release provenance
kind: bug
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/689
    at: 2026-11-21T20:49:44.475Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:38:49.263Z
updated_at: 2026-11-21T21:30:21.586Z
started_at: 2026-11-21T20:40:37.225Z
closed_at: 2026-11-21T21:30:21.584Z
close_reason: Merged as jlevy/metabrowser#689 after independent review, portable release fixtures and exact hosted general and native CI.
resolution: null
duplicate_of: null
---
The macOS build copies the shared Lucide glyph license from outside apps/macos; an uncommitted edit can currently go into a signed app stamped with a clean commit. Check the native packaging inputs consistently before the build and when stamping its source. Add a regression for changes to the shared file.
