---
type: is
id: is-01m7ktyej1wgp7sntjrbff1r4j
title: "PR #496 review A4: the Makefile sketch leaves the tier targets out of | install and .PHONY"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:23.041Z
updated_at: 2026-11-17T04:08:32.190Z
closed_at: 2026-11-17T04:08:32.190Z
close_reason: "Fixed in 8b4da0cb: the Makefile sketch puts test-parallel, test-serial, test-chrome, and test-goldens on .PHONY and the | install line; mb-dz35 says so."
resolution: null
duplicate_of: null
---
plan:271-295 against Makefile:33 and :54. A fresh CI job calling make test-parallel etc. directly would skip uv sync and npm ci.
