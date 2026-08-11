---
type: is
id: is-01kxramdcx05gn4fd0qyc7tfw0
title: Harden remote command launch and signal lifecycle
kind: bug
status: closed
priority: 1
version: 3
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:20:30.876Z
updated_at: 2026-07-17T15:54:16.529Z
closed_at: 2026-07-17T15:54:16.529Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
Convert missing or unlaunchable ssh/gcloud commands into actionable CLI errors, preserve exception causes internally, restore process signal handlers, forward termination signals, and normalize child signal exits to standard shell codes such as 130 and 143.
