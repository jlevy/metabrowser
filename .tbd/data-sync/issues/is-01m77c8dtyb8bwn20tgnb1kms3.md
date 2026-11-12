---
type: is
id: is-01m77c8dtyb8bwn20tgnb1kms3
title: "macOS app: a reopened folder's log claim must not collide with its retiring session (review E2, #363)"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels:
  - macos
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T07:58:48.157Z
updated_at: 2026-11-12T07:58:54.083Z
started_at: 2026-11-12T07:58:54.082Z
---
Review E2 on #363 (mb-niod): ServerLogLease tries only the shared log and .app-<pid>.log, assuming one session per root per app process, but ServerFleet.retire keeps a retiring session and its lease until shutdown completes. Reopening the folder then fails with 'another process holds it' and nothing retries. Fix: distinct fallback log names for overlapping sessions of one process, exclusivity kept; regression with a held shared lease and a slow-stopping same-owner session.
