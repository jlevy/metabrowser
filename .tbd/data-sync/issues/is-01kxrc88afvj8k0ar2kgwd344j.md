---
type: is
id: is-01kxrc88afvj8k0ar2kgwd344j
title: Keep upward port searches within the TCP range
kind: bug
status: closed
priority: 1
version: 3
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:48:49.614Z
updated_at: 2026-07-17T15:54:16.562Z
closed_at: 2026-07-17T15:54:16.562Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
Starting at a valid high port can make serve or remote probe ports above 65535, leading to OverflowError and a traceback. Bound every local and remote candidate range and cover an occupied port 65535.
