---
type: is
id: is-01kxramch25pwxfnk84vkachk5
title: Make top-level CLI errors and closed pipes Unix-safe
kind: bug
status: closed
priority: 1
version: 3
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:20:29.985Z
updated_at: 2026-07-17T15:54:16.505Z
closed_at: 2026-07-17T15:54:16.504Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
Eliminate tracebacks for expected CLIError failures, return stable nonzero codes, and treat downstream EPIPE as a quiet successful early close for help and streamed output. Add real entry-point regression tests.
