---
type: is
id: is-01m3wfpjbz1ktepk7e8a5c9yte
title: "Plan spec: a Pulls tab for mirrored repositories and local checkouts"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-10-01T19:40:13.053Z
updated_at: 2026-10-01T19:40:13.053Z
---
Write the design as a plan spec under docs/project/specs/active/ (after the v0.12 landing docs), from the notes on mb-lnkl (list data), mb-iw1v (the tab; automatic appearance; on-demand pull-request open) and mb-cbak (local checkouts). Cover: the five suggested PRs and their order; the rules to preserve (no startup gh or network on a plain folder; network only when the user opens the tab on a checkout; no writes to a user's repository; pull-request text always inert; bounded lists with honest counts); the open decisions for the user (which remote identifies the repository on a fork; before or after the v0.12 landing; row content; Files changed on a checkout when commits are missing). Update the thin-mirror plan's capability map and 'Later' line to point at it. No code.
