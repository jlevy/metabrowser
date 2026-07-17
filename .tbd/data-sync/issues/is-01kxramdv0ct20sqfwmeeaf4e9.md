---
type: is
id: is-01kxramdv0ct20sqfwmeeaf4e9
title: Make plugin diagnostics composable for people and agents
kind: bug
status: closed
priority: 1
version: 3
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:20:31.328Z
updated_at: 2026-07-17T15:54:16.536Z
closed_at: 2026-07-17T15:54:16.536Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
Give plugin show and doctor structured JSON output, keep data on stdout and diagnostics on stderr, and return nonzero when plugin discovery is only partially successful. Preserve readable text output and document the agent-facing contract.
