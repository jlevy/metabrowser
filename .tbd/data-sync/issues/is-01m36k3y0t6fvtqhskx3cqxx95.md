---
type: is
id: is-01m36k3y0t6fvtqhskx3cqxx95
title: "PR data: gh runner, PR records, refs/pull fetch, merge-base comparison, CLI inspection"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m36k3ydz3tgxmycjj8wknzq5
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:36:39.193Z
updated_at: 2026-09-23T07:36:39.614Z
---
Implements the PR-data row: bounded gh runner with auth-state checks (gh missing, logged out, account change discards results); gh as per-command credential helper for private fetches; gh api reads of the pull request, issue comments, reviews, review comments, check runs, statuses and files, stored as Pydantic-validated JSON records per pull request with fetch time and gh account, replaced atomically; fetch refs/pull/<n>/head; merge-base..head comparison; metab --api routes and goldens with a fake gh; seamless refresh for PR records. Independent review, make verify, green CI.
