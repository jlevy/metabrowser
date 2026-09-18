---
type: is
id: is-01m2tx5rx1aeacpnfzcr4h6hzk
title: "CI lint/audit fails on anyio 4.14.1 advisories (PRs #208 #210)"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: unknown@cursor
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-18T18:41:32.065Z
updated_at: 2026-09-18T18:41:38.619Z
started_at: 2026-09-18T18:41:38.619Z
---
Collapsed cache 1B-a PRs #208 (acquire-path) and #210 (cli-hygiene) fail the lint job because make lint-check audit runs uv audit, which reports GHSA-5p39-cfhj-2xmp, GHSA-82r6-8w77-94w6, and GHSA-3w57-8xmc-8v26 on locked anyio 4.14.1. Same SHAs were previously green as #145/#151. Upgrade the lock to anyio 4.14.2 (published 2026-07-12, past the 14-day cool-off) without changing product behavior. Do not flatten to main. Do not touch HTML or git-revision branches.
