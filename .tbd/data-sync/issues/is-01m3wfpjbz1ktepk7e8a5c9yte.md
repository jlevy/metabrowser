---
type: is
id: is-01m3wfpjbz1ktepk7e8a5c9yte
title: "Plan spec: a Pulls tab for mirrored repositories and local checkouts"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-10-01T19:40:13.053Z
updated_at: 2026-10-01T19:54:29.136Z
started_at: 2026-10-01T19:54:29.133Z
---
Write the design as a plan spec under docs/project/specs/active/ (after the v0.12 landing docs), from the notes on mb-lnkl (list data), mb-iw1v (the tab; automatic appearance; on-demand pull-request open) and mb-cbak (local checkouts). Cover: the five suggested PRs and their order; the rules to preserve (no startup gh or network on a plain folder; network only when the user opens the tab on a checkout; no writes to a user's repository; pull-request text always inert; bounded lists with honest counts); the open decisions for the user (which remote identifies the repository on a fork; before or after the v0.12 landing; row content; Files changed on a checkout when commits are missing). Update the thin-mirror plan's capability map and 'Later' line to point at it. No code.

## Notes

2026-10-01, decided by the user: 'we can land the stack first then continue a new stack with the pulls tab' and 'let's stabilize everything else but not implement the pulls tab yet, just make sure we've planned it well'. So: no implementation before the v0.12 stack lands; the plan spec (mb-qftx) is written now; the work starts afterwards as a new stack.
