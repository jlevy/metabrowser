---
type: is
id: is-01m2tx0n86bhjs21ezbjp9a6dz
title: "CI lint/audit fails on anyio 4.14.1 advisories (PR #209)"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: unknown@cursor
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-18T18:38:44.486Z
updated_at: 2026-09-18T18:38:51.940Z
started_at: 2026-09-18T18:38:51.940Z
---
The collapsed HTML trust PR lint job fails because make lint-check audit runs uv audit, which reports GHSA-5p39-cfhj-2xmp, GHSA-82r6-8w77-94w6, and GHSA-3w57-8xmc-8v26 on locked anyio 4.14.1. Upgrade the lock to anyio 4.14.2 (published 2026-07-12, past the 14-day cool-off) without changing product behavior.
