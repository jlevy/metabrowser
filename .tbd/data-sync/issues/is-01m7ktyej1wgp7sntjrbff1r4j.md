---
type: is
id: is-01m7ktyej1wgp7sntjrbff1r4j
title: "PR #496 review A4: the Makefile sketch leaves the tier targets out of | install and .PHONY"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:23.041Z
updated_at: 2026-11-17T04:06:23.041Z
---
plan:271-295 against Makefile:33 and :54. A fresh CI job calling make test-parallel etc. directly would skip uv sync and npm ci.
