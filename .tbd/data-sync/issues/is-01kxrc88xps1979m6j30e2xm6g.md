---
type: is
id: is-01kxrc88xps1979m6j30e2xm6g
title: Do not hide unrelated BrokenPipeError failures
kind: bug
status: closed
priority: 1
version: 3
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:48:50.230Z
updated_at: 2026-07-17T15:54:16.568Z
closed_at: 2026-07-17T15:54:16.568Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
The console entry point must treat only tracked stdout or stderr EPIPE as successful early consumer closure. Re-raise BrokenPipeError originating elsewhere and add a regression test.
