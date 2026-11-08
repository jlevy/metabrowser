---
type: is
id: is-01m6wkyht4d76t40kybbpah0fj
title: Keep Pulls-list usernames at the shared navigation metadata size
kind: bug
status: in_progress
priority: 1
version: 4
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
updated_at: 2026-11-08T04:12:32.770Z
started_at: 2026-11-08T03:41:47.857Z
---
Latest acceptance: use normal text color (black in the light theme), bold consistently for usernames and repository names. Introduce shared actor-name and repository-name design primitives and apply across PR list/page, comments/reviews/mergers and commit history/page/tooltip; branches retain shared colored copyable ref chips. Sidebar usernames and repo summaries use the same 12px metadata size; page actor/action/age retain their common larger size and baseline. Update the design system, plan and focused end-to-end evidence; install the reviewed build. Original November 7 acceptance: list usernames looked larger than the repository heading; the earlier muted-color preference is superseded by the latest normal-text-color request.
