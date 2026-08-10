---
type: is
id: is-01kzmt9pmz6zj09b1k6csdt8cs
title: "PR #24 review R5: Support SHA-256 repositories"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzmt94z25m0p0e3g531krnzy
created_at: 2026-08-10T03:08:43.038Z
updated_at: 2026-08-10T03:46:30.146Z
closed_at: 2026-08-10T03:46:30.146Z
close_reason: Fixed in 177e10f and 195b3e1; make verify and GitHub CI passed; all PR review threads replied to and resolved
---
Support full 64-character SHA-256 object IDs while preserving strict revision validation; src/metabrowser/git/wire.py:47; thread PRRT_kwDOTX174c6XusNY.
