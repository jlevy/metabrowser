---
type: is
id: is-01kxrbcqj2fh3rjr3nt6krc31e
title: Restore logging state after walk commands
kind: bug
status: closed
priority: 1
version: 4
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:33:47.712Z
updated_at: 2026-07-17T15:54:16.553Z
closed_at: 2026-07-17T15:54:16.553Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
CLI logging currently leaks captured streams across commands: walk leaves a handler attached, and server import installs a handler bound to whichever stdout was active. Repeated in-process commands can emit logging tracebacks, and performance diagnostics can pollute structured stdout. Scope walk logging state, route diagnostics to dynamically resolved stderr, and add cross-command regression coverage.
