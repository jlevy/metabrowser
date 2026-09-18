---
type: is
id: is-01m2tx5rx1aeacpnfzcr4h6hzk
title: "CI lint/audit fails on anyio 4.14.1 advisories (PRs #208 #210)"
kind: bug
status: closed
priority: 1
version: 4
delegate: unknown@cursor
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-18T18:41:32.065Z
updated_at: 2026-09-18T18:45:59.704Z
started_at: 2026-09-18T18:41:38.619Z
closed_at: 2026-09-18T18:45:59.704Z
close_reason: Lint job failures were real uv audit findings on anyio 4.14.1. acquire-path 68652585 and rebased cli-hygiene 26d68a47 lock anyio 4.14.2; GitHub lint is green on both PRs.
resolution: null
duplicate_of: null
---
Collapsed cache 1B-a PRs #208 (acquire-path) and #210 (cli-hygiene) fail the lint job because make lint-check audit runs uv audit, which reports GHSA-5p39-cfhj-2xmp, GHSA-82r6-8w77-94w6, and GHSA-3w57-8xmc-8v26 on locked anyio 4.14.1. Same SHAs were previously green as #145/#151. Upgrade the lock to anyio 4.14.2 (published 2026-07-12, past the 14-day cool-off) without changing product behavior. Do not flatten to main. Do not touch HTML or git-revision branches.

## Notes

Real lint-job failures on #208/#210: uv audit of anyio 4.14.1 (GHSA-5p39-cfhj-2xmp, GHSA-82r6-8w77-94w6, GHSA-3w57-8xmc-8v26). Not stale-name checks. acquire-path pushed 68652585; cli-hygiene rebased and force-pushed 26d68a47. Local make lint-check + audit passed on acquire-path. Hygiene audit clean after rebase.
