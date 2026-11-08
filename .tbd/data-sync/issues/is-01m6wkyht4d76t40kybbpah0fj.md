---
type: is
id: is-01m6wkyht4d76t40kybbpah0fj
title: Keep Pulls-list usernames at the shared navigation metadata size
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6wdjwawp9g1bvnefz2hxze3
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-08T03:41:34.403Z
updated_at: 2026-11-08T03:41:48.187Z
started_at: 2026-11-08T03:41:47.857Z
---
User acceptance on November 7: the username in a Pulls list row appears larger than the repository name above the list. Audit computed styles and shared author/avatar classes, make sidebar username text follow the surrounding navigation metadata size consistently, retain bold muted identity styling and smaller branch chips, and preserve the separate PR-page author/action/age baseline contract. Verify the built UI and focused production-session/design evidence; install the corrected build.
