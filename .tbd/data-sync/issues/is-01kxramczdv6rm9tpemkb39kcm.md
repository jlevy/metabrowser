---
type: is
id: is-01kxramczdv6rm9tpemkb39kcm
title: Validate CLI option values at the parser boundary
kind: bug
status: closed
priority: 1
version: 3
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:20:30.445Z
updated_at: 2026-07-17T15:54:16.523Z
closed_at: 2026-07-17T15:54:16.523Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
Move enum-like and numeric option validation into Typer parsing so invalid user input is rejected before execution with usage output and exit code 2. Cover formats, detail levels, log levels, ports, and walk limits without changing valid behavior.
