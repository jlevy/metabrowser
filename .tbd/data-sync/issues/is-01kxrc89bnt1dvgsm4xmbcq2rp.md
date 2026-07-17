---
type: is
id: is-01kxrc89bnt1dvgsm4xmbcq2rp
title: Tolerate the child-exit race while forwarding signals
kind: bug
status: closed
priority: 2
version: 3
labels:
  - cli
  - quality
dependencies: []
parent_id: is-01kxrakvth38d7qb684hn0rbt3
created_at: 2026-07-17T15:48:50.677Z
updated_at: 2026-07-17T15:54:16.574Z
closed_at: 2026-07-17T15:54:16.574Z
close_reason: Implemented with regression coverage; final make format verify passed all 703 tests plus lint, strict types, frontend checks, docs, hygiene, audits, build, and installed-distribution smoke tests.
---
The remote child may exit between poll and send_signal. Catch ProcessLookupError so normal Ctrl-C and termination shutdown do not produce a traceback, with a focused race test.
