---
type: is
id: is-01m87m2qhy6h5x0mrpkmx5an4v
title: Audit every reader-facing notice and error for internal or excessive detail
kind: task
status: in_progress
priority: 1
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/801
    at: 2026-11-25T00:08:31.316Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
hold: null
hold_until: null
created_at: 2026-11-24T20:31:11.931Z
updated_at: 2026-11-25T00:08:31.322Z
started_at: 2026-11-24T20:40:23.381Z
---
Find every message the app shows a reader (shell, built-in plugins, server error answers rendered on pages) that shows SHAs, commit lists, internal paths, exception text, schema locations, or mechanics, or that runs longer than a warning plus a remedy. Rewrite each to a short warning with at most one simple remedy, keeping details in route JSON where agents need them.
