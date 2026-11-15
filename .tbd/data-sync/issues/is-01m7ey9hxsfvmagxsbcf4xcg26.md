---
type: is
id: is-01m7ey9hxsfvmagxsbcf4xcg26
title: _LONG_LIVED_PATHS and comments name /api/tail, which has no route
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:40.504Z
updated_at: 2026-11-15T06:28:40.504Z
---
server.py _LONG_LIVED_PATHS lists /api/tail and events.py mentions it; no route is registered. Tailing uses /api/stream.
