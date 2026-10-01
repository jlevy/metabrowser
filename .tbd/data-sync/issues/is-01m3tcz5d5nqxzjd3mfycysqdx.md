---
type: is
id: is-01m3tcz5d5nqxzjd3mfycysqdx
title: A served commit the mirror lacks shows 'Could not load this commit.' instead of the fetch state
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T00:14:00.099Z
updated_at: 2026-10-01T04:37:41.717Z
started_at: 2026-10-01T00:14:25.881Z
closed_at: 2026-10-01T04:37:41.716Z
close_reason: "PR #249: typed commit_not_found; on a served mirror the page asks for one selection fetch only outside the freshness window (server-enforced floor), then shows found, 'Commit not found', 'Commit not fetched' or 'Could not load'; never claims a fetch that did not run. CI green."
resolution: null
duplicate_of: null
---
QA record (rerun on #243): navigating a served page to /commit/<oid> for a commit the mirror lacks shows 'Could not load this commit.' It was not checked whether this predates #243. Compare the /view/ selection_state pending/fetch_failed path ('Address not fetched').
