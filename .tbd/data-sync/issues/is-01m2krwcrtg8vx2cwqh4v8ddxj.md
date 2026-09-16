---
type: is
id: is-01m2krwcrtg8vx2cwqh4v8ddxj
title: "Hosted review Phase 0B.3a: implement the scrubbed GitHub coverage oracle"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b3
dependencies:
  - type: blocks
    target: is-01m2krwnemr6d0fht4kk7gsafx
parent_id: is-01m2k1jnf5t6bgg340skd537hn
created_at: 2026-09-16T00:11:49.398Z
updated_at: 2026-09-16T00:11:58.291Z
---
Implement the complete no-network Phase 0B.3 GitHub coverage oracle: scrubbed public fixtures, terminology-to-common-model mapping inventory, coverage and mapping tests, explicit observed/derived/optional-not-requested dispositions, hostile metadata, and future GitLab as a named consumer without speculative fields. Keep provider responses as test evidence only, never runtime input or a second model, on one formal branch stacked on the green Phase 0B.2 PR.
